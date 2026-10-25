"""Durable, bounded recovery of existing note jobs; never resends a mutation."""
import json
import os
from pathlib import Path
import re
import time
import uuid

from .core import CadenceError, sha256
from .bridge_rpc import RpcConnection


def durable_json(path, value):
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,allow_nan=False)
            stream.flush();os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def acquire_guard(directory):
    import msvcrt
    stream=(directory/'recovery.guard').open('a+b')
    if stream.tell()==0:stream.write(b'0');stream.flush()
    stream.seek(0)
    try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
    except OSError as error:
        stream.close()
        raise CadenceError('recovery_busy','Another apply or recovery owns this binding.') from error
    return stream


class GuiJobs:
    def _registered_paths(self):
        paths=set(self.gui.configs)
        for directory in self.gui.roots:
            root=directory.resolve(strict=True)
            for candidate in root.glob('gui-bridge-*/binding.json'):
                if candidate.resolve().is_relative_to(root):paths.add(candidate.resolve())
                if len(paths)>64:raise CadenceError('instance_limit','Too many registered bridge candidates.')
        return sorted(paths)

    def _job(self,plan_id):
        if not re.fullmatch('[a-f0-9]{32}',plan_id):raise CadenceError('invalid_job','Invalid job identity.')
        found=[]
        for binding in self._registered_paths():
            path=binding.parent/f'plan-{plan_id}.json'
            if path.exists():
                if path.is_symlink() or path.stat().st_size>65536:raise CadenceError('invalid_job','Invalid plan record.')
                row=json.loads(path.read_text(encoding='utf-8'))
                if row['plan']['planId']!=plan_id or self._digest(row['plan'])!=row['digest']:
                    raise CadenceError('invalid_job','Plan record digest mismatch.')
                found.append((binding,path,row))
        if len(found)!=1:raise CadenceError('job_not_found','Job is missing or ambiguous in registered bindings.')
        return found[0]

    def jobs(self):
        with self.gui.lock:
            rows=[]
            for binding in self._registered_paths():
                for path in sorted(binding.parent.glob('plan-*.json')):
                    if len(rows)>=256:raise CadenceError('result_limit','At most 256 job records may be listed.')
                    if path.is_symlink() or path.stat().st_size>65536:continue
                    row=json.loads(path.read_text(encoding='utf-8'));plan=row['plan']
                    state=row.get('state','planned')
                    if state=='planned' and plan['expiresAt']<time.time():state='expired'
                    rows.append({'planId':plan['planId'],'planDigest':row['digest'],'state':state,
                                 'property':plan['property'],'reference':plan['reference'],
                                 'createdAt':plan['createdAt'],'canReplayMutation':False})
            return {'jobs':rows,'automaticRecovery':False}

    def cancel(self,plan_id,plan_digest):
        with self.gui.lock:
            binding,path,row=self._job(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest does not match.')
            if row.get('state','planned')=='cancelled':return {'planId':plan_id,'cancelled':True}
            if row.get('state','planned') not in {'planned','expired'}:
                raise CadenceError('too_late','A possibly started write cannot be cancelled or rolled back.')
            # Same exclusive lock as apply closes the cross-server cancel/apply race.
            config=json.loads(binding.read_text(encoding='utf-8'))
            lock=Path(config['expectedDesign']).parent/'.cadence-mcp-write.lock'
            try:
                with lock.open('x',encoding='utf-8') as stream:json.dump({'planId':plan_id,'kind':'cancel'},stream)
            except FileExistsError as error:raise CadenceError('write_locked','An active or unresolved write owns this copy.') from error
            try:
                current=json.loads(path.read_text(encoding='utf-8'))
                if current.get('state','planned')!='planned':raise CadenceError('too_late','Plan is no longer pending.')
                row['state']='cancelled';durable_json(path,row)
                self.plans.pop(plan_id,None)
            finally:lock.unlink()
            return {'planId':plan_id,'cancelled':True,'designChanged':False}

    def recover(self,plan_id,plan_digest):
        with self.gui.lock:
            binding,path,row=self._job(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest does not match.')
            if row.get('state') not in {'started','verified','not_applied'}:raise CadenceError('recovery_not_needed','Job has not entered an uncertain write state.')
            config=json.loads(binding.read_text(encoding='utf-8'));design=Path(config['expectedDesign']).resolve(strict=True)
            if design.is_relative_to(self.config.install_root):raise CadenceError('write_denied','Installation cannot be a recovery target.')
            lock=design.parent/'.cadence-mcp-write.lock'
            if row.get('state') in {'verified','not_applied'} and not lock.exists():return {**row['result'],'recovered':True}
            if not lock.exists() or json.loads(lock.read_text(encoding='utf-8')).get('planId')!=plan_id:
                raise CadenceError('recovery_conflict','Write lock does not belong to this job.')
            # Nonblocking OS file lock prevents two recovery processes from verifying/publishing together.
            import msvcrt
            guard=binding.parent/'recovery.guard'
            with guard.open('a+b') as stream:
                if stream.tell()==0:stream.write(b'0');stream.flush()
                stream.seek(0)
                try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                except OSError as error:raise CadenceError('recovery_busy','Another recovery owns this binding.') from error
                try:
                    observed=sha256(design)
                    connection=RpcConnection(binding)
                    reply=connection.call('property.outcome',{'planId':plan_id},observed_fingerprint=observed)
                    native=reply['data']
                    if native.get('state')=='planned' and native.get('unchangedGeneration') is True and native.get('dirtyState')=='clean':
                        if observed!=row['plan']['baseFingerprint']:
                            raise CadenceError('state_indeterminate','Pending native plan but disk changed; preserve lock.')
                        connection.call('property.abandon',{'planId':plan_id})
                        if sha256(design)!=observed:raise CadenceError('target_changed','File changed during pending-plan retirement.')
                        result={'planId':plan_id,'disposition':'not_applied','saved':False,'designChanged':False,
                                'sourceFingerprintBefore':observed,'sourceFingerprintAfter':observed,'mutationReplayed':False}
                        row.update(state='not_applied',result=result);durable_json(path,row)
                        if row.get('ledgerName'):
                            name=row['ledgerName']
                            if not re.fullmatch(r'write-[a-f0-9]{64}\.json',name):raise CadenceError('invalid_job','Invalid ledger name.')
                            durable_json(binding.parent/name,{'state':'not_applied','planDigest':plan_digest,'result':result})
                        self._invalidate(config['instanceId']);lock.unlink()
                        return {**result,'recovered':True}
                    if native.get('state')!='saved' or native.get('unchangedGeneration') is not True or native.get('dirtyState')!='clean':
                        raise CadenceError('state_indeterminate','Capture cannot attest an unchanged completed save; no automatic recovery.')
                    result=self._verify(design,row['plan'])
                    if sha256(design)!=observed:raise CadenceError('target_changed','Design changed during recovery.')
                    # Repeat native attestation after independent work before releasing any lock.
                    again=connection.call('property.outcome',{'planId':plan_id},observed_fingerprint=observed)
                    if again['generation']!=reply['generation'] or again['data']!=native:
                        raise CadenceError('target_changed','GUI state changed during recovery.')
                    config['sourceFingerprint']=observed;durable_json(binding,config)
                    row.update(state='verified',result=result);durable_json(path,row)
                    if row.get('ledgerName'):
                        ledger=binding.parent/row['ledgerName']
                        if ledger.parent!=binding.parent or not re.fullmatch('write-[a-f0-9]{64}\\.json',ledger.name):
                            raise CadenceError('invalid_job','Invalid journal name.')
                        durable_json(ledger,{'state':'verified','planDigest':plan_digest,'result':result})
                    self._invalidate(config['instanceId']);lock.unlink()
                    return {**result,'recovered':True}
                finally:
                    stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
