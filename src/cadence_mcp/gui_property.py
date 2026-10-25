"""Experimental fixed-note write workflow on explicitly prepared fixture copies."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import time
import uuid

from .core import CadenceError,sha256,write_json
from .environment import run_tcl
from .gui_jobs import GuiJobs,durable_json,acquire_guard
from .gui_job_resolution import JobResolution
from .bridge_rpc import RpcConnection

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def connectivity(document):
    pages={row['objectId']:(row['schematicId'],row['name']) for row in document['page']}
    names={row['objectId']:row['name'] for row in document['schematic']}
    return sorted((names[pages[p['pageId']][0]],pages[p['pageId']][1],p['reference'],p['number'],p['net'],p['connected'])
                  for p in document['pin'])

class GuiPropertyWriter(JobResolution,GuiJobs):
    _digest=staticmethod(digest)
    def __init__(self,gui,config):
        self.gui=gui;self.config=config;self.plans={}

    def _binding(self,session_id):
        if session_id not in self.gui.sessions:raise CadenceError('session_lost','GUI session is not attached.')
        session=self.gui.sessions[session_id]
        if session.get('access')!='write':raise CadenceError('write_access_required','Attach an explicit write session on a prepared copy.')
        binding_path=session['connection'].path
        binding=json.loads(binding_path.read_text(encoding='utf-8'))
        design=Path(binding['expectedDesign']).resolve(strict=True)
        manifest_path=design.parent/'write-fixture.json'
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if (binding.get('allowPropertyWrite') is not True or manifest.get('kind')!='cadence-mcp-write-fixture-v1'
                or Path(manifest['design']).resolve()!=design or Path(manifest['source']).resolve()==design
                or not binding.get('writeLeaseId')):
            raise CadenceError('write_denied','Only an explicitly prepared isolated fixture copy permits note writes.')
        if design.is_relative_to(self.config.install_root):raise CadenceError('write_denied','Cannot write installation files.')
        return session,binding_path,binding,design

    def _snapshot(self,design):
        before=sha256(design)
        snapshot=design.parent/f'verify-copy-{uuid.uuid4().hex}.dsn'
        shutil.copyfile(design,snapshot)
        if sha256(snapshot)!=before or sha256(design)!=before:
            raise CadenceError('target_changed','Design changed while copying verification snapshot.')
        return snapshot

    def _inspect(self,design):
        snapshot=self._snapshot(design)
        output=design.parent/f'inspection-{uuid.uuid4().hex}.json'
        run_tcl(self.config,'inspect.tcl',[str(snapshot),str(output),'100000'],design.parent)
        if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Oversized inspection result.')
        result=json.loads(output.read_text(encoding='utf-8'))
        snapshot.unlink();output.unlink()
        return result

    def plan(self,session_id,schematic,page,reference,value):
        with self.gui.lock:
            if len(value)>512 or '\x00' in value:raise CadenceError('invalid_value','Note exceeds the supported format.')
            session,path,binding,design=self._binding(session_id)
            if (design.parent/'.cadence-mcp-write.lock').exists():raise CadenceError('write_locked','Resolve the existing job before making another plan.')
            if len(self.plans)>=64:
                for key,record in list(self.plans.items()):
                    if record.get('terminal') or time.time()>record['plan']['expiresAt']:self.plans.pop(key,None)
            if len(self.plans)>=64:raise CadenceError('plan_limit','At most 64 cached plans.')
            session["connection"].ready_for_write()
            before=sha256(design)
            baseline=self._inspect(design)
            plan_id=uuid.uuid4().hex
            reply=session['connection'].call('property.plan',{'sessionId':session_id,'generation':session['generation'],
                'planId':plan_id,'schematicName':schematic,'pageName':page,'reference':reference,'value':value})
            if before!=sha256(design):raise CadenceError('target_changed','Design changed during planning.')
            plan={'planId':plan_id,'sessionId':session_id,'generation':session['generation'],
                  'schematicName':schematic,'pageName':page,'reference':reference,'property':'MCP_NOTE','value':value,
                  'baseFingerprint':before,'expectedConnectivityHash':digest(connectivity(baseline)),
                  'oldExists':reply['data']['oldExists'],'oldValue':reply['data']['oldValue'],
                  'createdAt':time.time(),'expiresAt':time.time()+55}
            plan_digest=digest(plan)
            self.plans[plan_id]={'plan':plan,'digest':plan_digest}
            durable_json(path.parent/f'plan-{plan_id}.json',{'plan':plan,'digest':plan_digest,'state':'planned'})
            return {'plan':plan,'planDigest':plan_digest,'applied':False}

    def apply(self,plan_id,plan_digest,idempotency_key):
        with self.gui.lock:
            if plan_id not in self.plans:raise CadenceError('stale_plan','Plan belongs to another server or is unknown.')
            record=self.plans[plan_id];plan=record['plan']
            if plan_digest!=record['digest']:raise CadenceError('plan_digest_mismatch','Plan digest does not match the preview.')
            # The ledger location is fixed by the prepared binding, never by request input.
            session_id=plan['sessionId']
            binding_path=record.get('bindingPath')
            if binding_path is None:
                session,binding_path,binding,design=self._binding(session_id)
                record['bindingPath']=binding_path
            else:
                binding=json.loads(binding_path.read_text(encoding='utf-8'));design=Path(binding['expectedDesign'])
            key=digest({'key':idempotency_key})
            ledger=binding_path.parent/f'write-{key}.json'
            if ledger.exists():
                previous=json.loads(ledger.read_text(encoding='utf-8'))
                if previous['planDigest']!=plan_digest:raise CadenceError('idempotency_conflict','Key already belongs to another plan.')
                if previous['state']=='verified':return {**previous['result'],'idempotentReplay':True}
                raise CadenceError('state_indeterminate','Earlier request may have written; it is not replayed.')
            session,binding_path,binding,design=self._binding(session_id)
            plan_path=binding_path.parent/f'plan-{plan_id}.json'
            disk=json.loads(plan_path.read_text(encoding='utf-8'))
            if disk.get('state','planned')!='planned':raise CadenceError('stale_plan','Plan is cancelled or already started.')
            if time.time()>plan['expiresAt'] or sha256(design)!=plan['baseFingerprint']:
                raise CadenceError('stale_plan','Plan expired or source changed.')
            session['connection'].ready_for_write()
            lock=design.parent/'.cadence-mcp-write.lock'
            try:
                with lock.open('x',encoding='utf-8') as stream:json.dump({'planId':plan_id,'pid':os.getpid()},stream)
            except FileExistsError as error:raise CadenceError('write_locked','Another write or unresolved request owns this copy.') from error
            started=False;guard=None
            try:
                guard=acquire_guard(binding_path.parent)
                disk=json.loads(plan_path.read_text(encoding='utf-8'))
                if disk.get('state','planned')!='planned':raise CadenceError('stale_plan','Plan was cancelled before exclusive ownership.')
                disk.update(state='started',ledgerName=ledger.name)
                durable_json(plan_path,disk)
                durable_json(ledger,{'state':'started','planDigest':plan_digest,'planId':plan_id})
                started=True
                if not hasattr(self.gui,'active_operations'):self.gui.active_operations={}
                self.gui.active_operations[session['instanceId']]={'kind':'note_write','planId':plan_id}
                reply=session['connection'].call('property.apply',{'sessionId':session_id,'generation':session['generation'],
                    'planId':plan_id,'leaseId':binding['writeLeaseId']})
                if reply['data'].get('saved') is not True:raise CadenceError('save_failed','Native save was not confirmed.')
                result=self._verify(design,plan)
                receipt=session['connection'].call('property.outcome',{'planId':plan_id},observed_fingerprint=result['sourceFingerprintAfter'])
                if receipt['data'].get('state')!='saved' or receipt['data'].get('unchangedGeneration') is not True or receipt['data'].get('dirtyState')!='clean':
                    raise CadenceError('state_indeterminate','GUI changed during verification; retain the write lock for investigation.')
                # Only an independently verified own write may advance the host's expected fingerprint.
                binding['sourceFingerprint']=result['sourceFingerprintAfter']
                durable_json(binding_path,binding)
                disk.update(state='verified',result=result);durable_json(plan_path,disk)
                durable_json(ledger,{'state':'verified','planDigest':plan_digest,'result':result})
                self._invalidate(session['instanceId'])
                lock.unlink()
                record['terminal']=True
                try:
                    RpcConnection(binding_path).call('property.ack',{'planId':plan_id})
                    result['nativeReceiptReleased']=True
                except CadenceError:result['nativeReceiptReleased']=False
                return result
            except Exception as error:
                if not started:lock.unlink(missing_ok=True)
                else:self._invalidate(session['instanceId'])
                # Once a send is possible the durable ledger/lock survive for explicit recovery.
                if isinstance(error,CadenceError):raise
                raise CadenceError('state_indeterminate','Write outcome requires manual recovery; not replayed.') from error

            finally:
                if hasattr(self.gui,'active_operations'):self.gui.active_operations.pop(session['instanceId'],None)
                if guard is not None:guard.close()

    def _invalidate(self,instance_id):
        for sid,item in list(self.gui.sessions.items()):
            if item['instanceId']==instance_id:self.gui.sessions.pop(sid,None)
        self.gui.instances.pop(instance_id,None)

    def _verify(self,design,plan):
        saved_hash=sha256(design)
        after=self._inspect(design)
        output=design.parent/f'property-{uuid.uuid4().hex}.json'
        property_snapshot=self._snapshot(design)
        run_tcl(self.config,'verify_property.tcl',[str(property_snapshot),str(output),plan['schematicName'],plan['pageName'],plan['reference']],design.parent)
        actual=json.loads(output.read_text(encoding='utf-8'))
        if actual!={'exists':True,'value':plan['value']}:
            raise CadenceError('reopen_failed','Independent reader did not find the planned note.')
        if digest(connectivity(after))!=plan['expectedConnectivityHash']:
            raise CadenceError('connectivity_mismatch','Definition-level pin-net mapping changed.')
        if sha256(design)!=saved_hash:raise CadenceError('target_changed','Design changed during independent verification.')
        property_snapshot.unlink();output.unlink()
        return {'planId':plan['planId'],'property':'MCP_NOTE','saved':True,'reopened':True,
                'propertyMatched':True,'definitionConnectivityMatched':True,'occurrenceConnectivityVerified':False,
                'sourceFingerprintBefore':plan['baseFingerprint'],'sourceFingerprintAfter':saved_hash,
                'idempotentReplay':False,'requiresNewGuiSession':True}
