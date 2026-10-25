"""Native reference-map receipt loss/recovery, startup cancel and actual timeout."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import CaptureReferenceEdits
class LoseReceipt(CaptureReferenceEdits):
    def verify(self,directory,p,native_completed):
        if native_completed:
            (directory/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned receipt removed after native completion.')
        return super().verify(directory,p,native_completed)
class CancelAtStart(CaptureReferenceEdits):
    def execute(self,directory,p,cancel,on_started):
        def started(pid):on_started(pid);cancel.set()
        return super().execute(directory,p,cancel,started)
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);report={'passed':False,'cases':[],'sourceHashBefore':sha256(a.source)}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',CaptureReferenceEdits)]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        normal=Config(a.install_root,root/mode,(a.source.parent,),60);cap=CaptureService(normal);sid=cap.open(cap.create_workspace(str(a.source))['workspaceId'])['sessionId'];parts=cap.sessions[sid]['data']['part']
        config=Config(a.install_root,root/mode,(a.source.parent,),1 if mode=='native_timeout' else 60);writer=cls(config,cap)
        mapping=[{'partId':next(p['objectId'] for p in parts if p['reference']==old),'newReference':new} for old,new in [('R101','R102'),('R102','R101')]]
        plan=writer.plan(sid,mapping);row['plan']=plan
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as error:
            assert error.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout'}[mode],error.code;row['errorCode']=error.code
        else:raise AssertionError('Expected native fault not seen')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'));row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
        if mode=='receipt_loss':
            before=sha256(directory/'design.dsn');fresh=CaptureReferenceEdits(normal,CaptureService(normal));result=fresh.recover(plan['planId'],plan['planDigest'])
            assert result['state']=='verified_recovered' and result['nativeCompletionVerified'] is False and result['artifact']['sha256']==before==sha256(directory/'design.dsn')
            fresh.open_output(plan['planId'],plan['planDigest']);row['recovered']=result
        else:
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as error:assert error.code=='write_not_replayed'
            else:raise AssertionError('Faulted map replayed')
        row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
