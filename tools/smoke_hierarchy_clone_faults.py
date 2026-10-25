"""Native completion receipt loss and real start-window cancel/timeout acceptance."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_hierarchy_edit import CaptureHierarchyEdits
class LoseReceipt(CaptureHierarchyEdits):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned fixture removes receipt after native completion.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureHierarchyEdits):
 def execute(self,d,p,cancel,on_started):
  def started(pid):on_started(pid);cancel.set()
  return super().execute(d,p,cancel,started)
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','oracle'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);pins=[{k:p[k] for k in ('name','number','hotSpot')} for p in json.loads(a.oracle.read_text())['geometry']['pins']]
report={'passed':False,'cases':[],'sourceBefore':sha256(a.source)}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('timeout',CaptureHierarchyEdits)]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  normal=Config(a.install_root,root/mode,(a.source.parent,),60);capture=CaptureService(normal);ws=capture.create_workspace(str(a.source));sid=capture.open(ws['workspaceId'])['sessionId'];part=next(p for p in capture.sessions[sid]['data']['part'] if p['reference']=='halfadd_A')
  cfg=Config(a.install_root,root/mode,(a.source.parent,),1 if mode=='timeout' else 60);writer=cls(cfg,capture);plan=writer.plan(sid,part['objectId'],'halfadd_C',[2000,2000],pins);row['plan']=plan
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as e:assert e.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','timeout':'timeout'}[mode],e.code;row['errorCode']=e.code
  else:raise AssertionError('Expected owned native fault not observed')
  d=writer.root/('plan-'+plan['planId']);ledger=json.loads((d/'plan.json').read_text());row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
  if mode=='receipt_loss':
   before=sha256(d/'design.dsn');fresh=CaptureHierarchyEdits(normal,CaptureService(normal));recovered=fresh.recover(plan['planId'],plan['planDigest']);assert recovered['state']=='verified_recovered' and not recovered['nativeCompletionVerified'] and recovered['artifact']['sha256']==before==sha256(d/'design.dsn');fresh.open_output(plan['planId'],plan['planDigest']);row['recovered']=recovered
  else:
   try:writer.apply(plan['planId'],plan['planDigest'],mode)
   except CadenceError as e:assert e.code=='write_not_replayed'
   else:raise AssertionError('Mutation replayed')
  row['passed']=True
 except BaseException as e:row.update(error=str(e),errorType=type(e).__name__)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceBefore']==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
