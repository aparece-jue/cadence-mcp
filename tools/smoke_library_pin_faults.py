"""Real native edited OLB receipt-loss recovery and bounded process controls."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_edit import LibraryPinEdits

class LoseReceipt(LibraryPinEdits):
    def verify(self,directory,p,native_completed):
        if native_completed:
            (directory/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned test removes native receipt after completion.')
        return super().verify(directory,p,native_completed)
class CancelAtStart(LibraryPinEdits):
    def execute(self,directory,p,cancel,on_started):
        def started(pid):on_started(pid);cancel.set()
        return super().execute(directory,p,cancel,started)
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);report={'passed':False,'cases':[],'sourceHashBefore':sha256(a.source)}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',LibraryPinEdits)]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        normal=Config(a.install_root,root/mode,(a.source.parent,),60);library=LibraryService(normal);opened=library.open(str(a.source));sid=opened['libraryId'];target=next(p for p in library.sessions[sid]['data']['pin'] if p['position']==0)
        config=Config(a.install_root,root/mode,(a.source.parent,),1 if mode=='native_timeout' else 60);writer=cls(config,library)
        plan=writer.plan(sid,target['objectId'],name='FAULT_TEST');row['plan']=plan
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as e:
            assert e.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout'}[mode],e.code;row['errorCode']=e.code
        else:raise AssertionError('Expected owned native fault not observed')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'));row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
        if mode=='receipt_loss':
            before=sha256(directory/'library.olb');fresh=LibraryPinEdits(normal,LibraryService(normal));res=fresh.recover(plan['planId'],plan['planDigest'])
            assert res['state']=='verified_recovered' and res['nativeCompletionVerified'] is False and res['artifact']['sha256']==before==sha256(directory/'library.olb')
            opened=fresh.open_output(plan['planId'],plan['planDigest']);assert any(p['name']=='FAULT_TEST' for p in fresh.library.sessions[opened['libraryId']]['data']['pin']);row['recovered']=res
        else:
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as e:assert e.code=='write_not_replayed'
            else:raise AssertionError('Mutation replayed')
        row['passed']=True
    except BaseException as e:row.update(errorType=type(e).__name__,error=str(e))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
