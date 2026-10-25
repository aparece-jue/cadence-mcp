"""Actual model parameter worker faults, frozen input and unrelated-property corruption rejection."""
import argparse,copy,json,traceback
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import CapturePropertyEdits
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process

class LostReceipt(CapturePropertyEdits):
 def verify(self,d,p,native_completed):
  if native_completed:
   (d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned receipt removed after worker completion.')
  return super().verify(d,p,native_completed)
class Cancel(CapturePropertyEdits):
 def execute(self,d,p,cancel,on_started):
  def start(pid):on_started(pid);cancel.set()
  return super().execute(d,p,cancel,start)
class CorruptUnrelated(CapturePropertyEdits):
 def execute(self,d,p,cancel,on_started):
  process=super().execute(d,p,cancel,on_started);assert process['returnCode']==0
  session=next(iter(self.capture.sessions.values()));data=session['data'];names={r['objectId']:r['name'] for r in data['schematic']}
  other=next(r for r in data['part'] if names[r['schematicId']]=='ROOT' and r['reference']=='R10')
  q=copy.deepcopy(p);q.update(partId=other['objectId'],reference='R10',property='TC2',oldValue='0',value='7')
  argv=self.native_command(d,q);argv[4]=d/'unrelated-property-receipt.json'
  second=run_owned_process(argv,d,process_env(self.config),60,cancel=cancel,on_started=on_started)
  assert second['returnCode']==0 and second['remainingOwnedProcesses']==0
  (d/'unrelated-property-process.json').write_text(json.dumps(second,indent=2),encoding='utf-8')
  return process

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[]}
for mode,cls,code in [('receipt_loss',LostReceipt,'receipt_lost_fixture'),('cancel_at_start',Cancel,'operation_cancelled'),('native_timeout',CapturePropertyEdits,'timeout'),('unrelated_property_changed',CorruptUnrelated,'unexpected_property_change'),('changed_source',CapturePropertyEdits,'target_changed')]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  normal=Config(a.install_root,root/mode,(a.source.parent,),60);capture=CaptureService(normal);ws=capture.create_workspace(str(a.source));sid=capture.open(ws['workspaceId'])['sessionId']
  data=capture.sessions[sid]['data'];names={r['objectId']:r['name'] for r in data['schematic']};part=next(r for r in data['part'] if names[r['schematicId']]=='ROOT' and r['reference']=='R1')
  writer=cls(normal,capture);plan=writer.plan(sid,part['objectId'],'TC1','0.001');row['plan']=plan
  if mode=='native_timeout':writer.config=Config(a.install_root,root/mode,(a.source.parent,),1)
  if mode=='changed_source':
   source=capture.sessions[sid]['design'];source.write_bytes(source.read_bytes()+b'owned frozen snapshot tamper')
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as error:assert error.code==code,error.code;row['errorCode']=error.code
  else:raise AssertionError('Expected refusal absent')
  d,_,ledger=writer._load(plan['planId'])
  if mode=='changed_source':assert ledger['state']=='planned' and not (d/'design.dsn').exists()
  else:assert ledger['process']['remainingOwnedProcesses']==0;row['process']=ledger['process']
  if mode=='receipt_loss':
   before=sha256(d/'design.dsn');fresh=CapturePropertyEdits(normal,CaptureService(normal));result=fresh.recover(plan['planId'],plan['planDigest'])
   assert result['state']=='verified_recovered' and result['nativeCompletionVerified'] is False and result['effectivePropertyMultisetPreserved']
   assert sha256(d/'design.dsn')==before;row['recovered']=result
  elif mode!='changed_source':
   try:writer.apply(plan['planId'],plan['planDigest'],mode)
   except CadenceError as e:assert e.code=='write_not_replayed'
   else:raise AssertionError('Mutation replayed')
   try:writer.open_output(plan['planId'],plan['planDigest'])
   except CadenceError as e:assert e.code=='output_unverified'
   else:raise AssertionError('Unverified output opened')
  row['passed']=True
 except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(r['passed'] for r in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
