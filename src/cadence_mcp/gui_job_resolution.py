"""Two-phase, explicit closure of crashed jobs; never replays or rolls back a design write."""
import json
from pathlib import Path
import re
import time
import uuid
from .core import CadenceError,sha256
from .bridge_diagnostics import process_status
from .gui_jobs import acquire_guard,durable_json
from .environment import run_tcl

class JobResolution:
    def _resolution_context(self,plan_id,plan_digest):
        binding,path,row=self._job(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest does not match.')
        cfg=json.loads(binding.read_text(encoding='utf-8'))
        design=Path(cfg['expectedDesign']).resolve(strict=True)
        if design.is_relative_to(self.config.install_root):raise CadenceError('write_denied','Cannot resolve an installation design.')
        manifest=json.loads((design.parent/'write-fixture.json').read_text(encoding='utf-8'))
        if (not cfg.get('allowPropertyWrite') or manifest.get('kind')!='cadence-mcp-write-fixture-v1'
                or Path(manifest['design']).resolve()!=design or Path(manifest['source']).resolve()==design):
            raise CadenceError('write_denied','Resolution requires an explicitly prepared fixture copy.')
        return binding,path,row,cfg,design

    def review(self,plan_id,plan_digest):
        with self.gui.lock:
            binding,path,row,cfg,design=self._resolution_context(plan_id,plan_digest)
            if row.get('state')!='started':raise CadenceError('recovery_not_needed','Only unresolved started jobs need a forensic review.')
            if process_status(cfg['expectedPid'])!='stopped':raise CadenceError('process_not_stopped','Use native recovery first; manual closure requires proof that the old Capture process has stopped.')
            guard=acquire_guard(binding.parent)
            try:
                lock=design.parent/'.cadence-mcp-write.lock'
                if not lock.exists() or json.loads(lock.read_text(encoding='utf-8')).get('planId')!=plan_id:
                    raise CadenceError('recovery_conflict','Lock does not belong to this job.')
                before=sha256(design);plan=row['plan'];choices=[];observed={}
                if before==plan['baseFingerprint']:choices.append('close_unchanged')
                try:
                    verified=self._verify(design,plan)
                    observed={'plannedPropertyMatched':True,'definitionConnectivityMatched':True}
                    choices.append('accept_saved_artifact')
                except CadenceError as error:
                    observed={'savedArtifactVerified':False,'verificationCode':error.code}
                if sha256(design)!=before:raise CadenceError('target_changed','Design changed during forensic review.')
                review={'reviewId':uuid.uuid4().hex,'planId':plan_id,'planDigest':plan_digest,
                        'fileFingerprint':before,'oldPid':cfg['expectedPid'],'allowedDecisions':choices,
                        'observed':observed,'nativeCompletionVerified':False,'mutationReplayed':False,
                        'createdAt':time.time(),'expiresAt':time.time()+600}
                digest=self._digest(review)
                durable_json(binding.parent/f"review-{review['reviewId']}.json",{'review':review,'reviewDigest':digest})
                return {'review':review,'reviewDigest':digest,'lockReleased':False,'requiresExplicitDecision':True}
            finally:guard.close()

    def resolve(self,plan_id,plan_digest,review_id,review_digest,decision):
        with self.gui.lock:
            binding,path,row,cfg,design=self._resolution_context(plan_id,plan_digest)
            if not re.fullmatch('[a-f0-9]{32}',review_id):raise CadenceError('invalid_review','Invalid review identity.')
            file=binding.parent/f'review-{review_id}.json'
            if file.is_symlink() or file.stat().st_size>65536:raise CadenceError('invalid_review','Invalid review file.')
            record=json.loads(file.read_text(encoding='utf-8'));review=record['review']
            if (record['reviewDigest']!=review_digest or self._digest(review)!=review_digest
                    or review['planId']!=plan_id or review['planDigest']!=plan_digest):
                raise CadenceError('invalid_review','Review digest or job binding does not match.')
            if decision not in review['allowedDecisions']:raise CadenceError('resolution_denied','Decision is not supported by the independent evidence.')
            lock=design.parent/'.cadence-mcp-write.lock'
            terminal='resolved_saved_artifact' if decision=='accept_saved_artifact' else 'resolved_unchanged'
            if row.get('state')==terminal and not lock.exists():
                if row['result'].get('reviewDigest')!=review_digest:raise CadenceError('resolution_conflict','Job was closed using another review.')
                return {**row['result'],'idempotentReplay':True}
            if row.get('state') not in {'started',terminal}:raise CadenceError('resolution_conflict','Job is no longer unresolved.')
            guard=acquire_guard(binding.parent)
            try:
                if (process_status(cfg['expectedPid'])!='stopped' or time.time()>review['expiresAt']
                        or sha256(design)!=review['fileFingerprint']):
                    raise CadenceError('stale_review','Process, file or review validity changed; preserve the lock and review again.')
                if not lock.exists() or json.loads(lock.read_text(encoding='utf-8')).get('planId')!=plan_id:
                    raise CadenceError('recovery_conflict','Lock does not belong to this job.')
                current=json.loads(path.read_text(encoding='utf-8'))
                if current.get('state') not in {'started',terminal}:raise CadenceError('resolution_conflict','Job changed while acquiring exclusive ownership.')
                result={'planId':plan_id,'disposition':terminal,'reviewDigest':review_digest,'decision':decision,
                        'fileFingerprint':review['fileFingerprint'],'lockReleased':True,'designChanged':False,
                        'nativeCompletionVerified':False,'savedArtifactVerified':decision=='accept_saved_artifact',
                        'mutationReplayed':False,'idempotentReplay':False,'requiresNewBinding':True}
                # Audit evidence is written before the terminal job state. A crash leaves the lock for an idempotent retry.
                audit=binding.parent/f'resolution-{review_id}.json'
                durable_json(audit,{'result':result,'originalPlanDigest':plan_digest,'resolvedAt':time.time()})
                row.update(state=terminal,result=result);durable_json(path,row)
                if row.get('ledgerName'):
                    name=row['ledgerName']
                    if not re.fullmatch(r'write-[a-f0-9]{64}\.json',name):raise CadenceError('invalid_job','Invalid ledger name.')
                    durable_json(binding.parent/name,{'state':terminal,'planDigest':plan_digest,'result':result})
                self._invalidate(cfg['instanceId']);self.plans.pop(plan_id,None);lock.unlink()
                return result
            finally:guard.close()
