"""Owned package-reference failure/recovery matrix; no replay and no original mutation."""
import argparse,json,traceback
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import CaptureReferenceEdits,read_units
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process

class LostReceipt(CaptureReferenceEdits):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned receipt removed after save.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureReferenceEdits):
 def execute(self,d,p,cancel,on_started):
  def start(pid):
   on_started(pid);row=self._load(d.name.removeprefix('plan-'))[2];assert self.cancel(row['plan']['planId'],row['digest'])['cancelRequested']
  return super().execute(d,p,cancel,start)
class CorruptUnrelated(CaptureReferenceEdits):
 def execute(self,d,p,cancel,on_started):
  process=super().execute(d,p,cancel,on_started);assert process['returnCode']==0
  units=read_units(self.capture,next(iter(self.capture.sessions)));affected={r['nativeId'] for r in p['changes']}
  unit=next(u for u in units.values() if u['kind']=='placed' and u['nativeId'] not in affected)
  evidence=json.loads(Path(p['expectedEvidence']).read_text(encoding='utf-8'));state=next(r for r in evidence['state'] if r['nativeId']==unit['nativeId']);old=next(v['value'] for v in state['effective'] if v['name']=='Value')
  argv=[self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_property.tcl',self.config.install_root,d/'design.dsn',d/'unrelated-change.json',unit['partId'],'100000','Value',old,'CORRUPT_UNRELATED',unit['schematicName'],unit['pageName'],unit['reference']]
  changed=run_owned_process(argv,d,process_env(self.config),60,cancel=cancel,on_started=on_started);assert changed['returnCode']==0 and changed['remainingOwnedProcesses']==0
  (d/'unrelated-process.json').write_text(json.dumps(changed,indent=2),encoding='utf-8');return process

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();a.install_root=a.install_root.resolve();fixture=a.fixture_root.resolve();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
prior=json.loads((fixture/'report.json').read_text(encoding='utf-8'));source=fixture/'work'/prior['cases'][0]['result']['outputWorkspaceRelativePath']/'design.dsn'
report={'passed':False,'sourceHashBefore':sha256(source),'cases':[]}
for mode,cls,code in [('receipt_loss',LostReceipt,'receipt_lost_fixture'),('cancel_at_start',CancelAtStart,'operation_cancelled'),('native_timeout',CaptureReferenceEdits,'timeout'),('unrelated_instance_changed',CorruptUnrelated,'package_reference_state_mismatch'),('changed_source',CaptureReferenceEdits,'target_changed'),('changed_expectation',CaptureReferenceEdits,'target_changed')]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  c=Config(a.install_root,root/mode,(fixture,),60);cap=CaptureService(c);writer=cls(c,cap);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];units=read_units(cap,sid);owner=next(u for u in units.values() if u['reference']=='U501' and u['deviceDesignator']=='A')
  plan=writer.plan_packages(sid,[{'partId':owner['partId'],'newReference':'U601'}]);row['plan']=plan;payload=writer._load(plan['planId'])[2]['plan']['payload']
  if mode=='native_timeout':writer.config=Config(a.install_root,root/mode,(fixture,),1)
  if mode in ('changed_source','changed_expectation'):
   file=Path(payload['sourceDesign' if mode=='changed_source' else 'expectedEvidence']);file.write_bytes(file.read_bytes()+b'owned frozen input tamper')
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as e:assert e.code==code,e.code;row['errorCode']=e.code
  else:raise AssertionError('Expected refusal absent')
  d,_,ledger=writer._load(plan['planId'])
  if mode.startswith('changed_'):assert ledger['state']=='planned' and not (d/'design.dsn').exists()
  else:
   row['process']=ledger['process'];assert row['process']['remainingOwnedProcesses']==0 and row['process']['rootExitSignalConfirmed'] and row['process']['observedProcessExitSignalsConfirmed']
   if mode=='native_timeout':assert row['process']['state']=='timeout'
   if mode=='receipt_loss':
    before=sha256(d/'design.dsn');fresh=CaptureReferenceEdits(c,CaptureService(c));result=fresh.recover(plan['planId'],plan['planDigest']);assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and result['oldNewNodeTableVerified'];assert sha256(d/'design.dsn')==before;row['recovered']=result
   else:
    try:writer.open_output(plan['planId'],plan['planDigest'])
    except CadenceError as e:assert e.code=='output_unverified'
    else:raise AssertionError('Unverified output opened')
    try:writer.apply(plan['planId'],plan['planDigest'],mode)
    except CadenceError as e:assert e.code=='write_not_replayed'
    else:raise AssertionError('Mutation replayed')
  row['passed']=True
 except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(source);report['passed']=all(r['passed'] for r in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
