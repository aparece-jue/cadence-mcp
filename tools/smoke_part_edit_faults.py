"""Native receipt loss/recovery, start-window cancellation and actual timeout."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_part_edit import CapturePartEdits

class LoseReceipt(CapturePartEdits):
    def verify(self,directory,p,native_completed):
        if native_completed:
            (directory/'native-result.json').unlink()
            raise CadenceError('receipt_lost_fixture','Owned test removes receipt after native completion.','verify')
        return super().verify(directory,p,native_completed)

class CancelAtStart(CapturePartEdits):
    def execute(self,directory,p,cancel,on_started):
        def started(pid):on_started(pid);cancel.set()
        return super().execute(directory,p,cancel,started)

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[]}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',CapturePartEdits)]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        # Plan reads need their normal timeout; only actual execution uses 1 second.
        normal=Config(a.install_root,root/mode,(a.source.parent,),60);cap=CaptureService(normal);ws=cap.create_workspace(str(a.source));sid=cap.open(ws['workspaceId'])['sessionId']
        part=next(p for p in cap.sessions[sid]['data']['part'] if p['reference']=='R401')
        config=Config(a.install_root,root/mode,(a.source.parent,),1 if mode=='native_timeout' else 60)
        writer=cls(config,cap)
        expected=[{'schematicName':'HALFADD','pageName':'MCP_EMPTY_ACCEPT','reference':'R401','pinNumber':n,'connected':False,'net':None} for n in ('1','2')]
        pins=[{'number':'1','name':'A','hotSpot':[680,500]},{'number':'2','name':'B','hotSpot':[720,500]}]
        plan=writer.plan(sid,part['objectId'],'set_pose',expected,[700,500],0,0,pins);row['plan']=plan
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as error:
            wanted={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout'}[mode]
            assert error.code==wanted,(error.code,wanted);row['errorCode']=error.code
        else:raise AssertionError('Expected native fault not observed')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'));row['process']=ledger['process']
        assert ledger['process']['remainingOwnedProcesses']==0
        if mode=='receipt_loss':
            before=sha256(directory/'design.dsn');fresh=CapturePartEdits(normal,CaptureService(normal))
            recovered=fresh.recover(plan['planId'],plan['planDigest'])
            assert recovered['state']=='verified_recovered' and recovered['nativeCompletionVerified'] is False
            assert recovered['artifact']['sha256']==before==sha256(directory/'design.dsn')
            fresh.open_output(plan['planId'],plan['planDigest']);row['recovered']=recovered
        else:
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as e:assert e.code=='write_not_replayed'
            else:raise AssertionError('Faulted mutation replayed')
        row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
