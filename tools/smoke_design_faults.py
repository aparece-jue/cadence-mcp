"""Native creation receipt loss, startup cancel, and real timeout; never replay."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_design_create import CaptureDesignCreates

class LoseReceipt(CaptureDesignCreates):
    def verify(self,directory,p,native_completed):
        if native_completed:
            (directory/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned native receipt removed after completion.')
        return super().verify(directory,p,native_completed)
class CancelAtStart(CaptureDesignCreates):
    def execute(self,directory,p,cancel,on_started):
        def started(pid):on_started(pid);cancel.set()
        return super().execute(directory,p,cancel,started)
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);report={'passed':False,'cases':[]}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',CaptureDesignCreates)]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        config=Config(a.install_root,root/mode,(root,),1 if mode=='native_timeout' else 60)
        writer=cls(config,CaptureService(config));plan=writer.plan('ROOT','PAGE');row['plan']=plan
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as error:
            assert error.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout'}[mode];row['errorCode']=error.code
        else:raise AssertionError('Expected native fault not seen')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'));row['process']=ledger['process'];assert row['process']['remainingOwnedProcesses']==0
        if mode=='receipt_loss':
            before=sha256(directory/'design.dsn');fresh=CaptureDesignCreates(config,CaptureService(config));res=fresh.recover(plan['planId'],plan['planDigest'])
            assert res['state']=='verified_recovered' and not res['nativeCompletionVerified'] and res['artifact']['sha256']==before==sha256(directory/'design.dsn')
            opened=fresh.open_output(plan['planId'],plan['planDigest']);assert opened['counts']=={'schematic':1,'page':1,'part':0,'pin':0};row['recovered']=res
        else:
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as error:assert error.code=='write_not_replayed'
            else:raise AssertionError('Failed/cancelled creation replayed')
        row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
