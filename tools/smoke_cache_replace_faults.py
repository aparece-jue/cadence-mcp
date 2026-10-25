"""Native compatible-cache task failures and verify-only recovery; every mutation stays owned."""
import argparse,copy,json,traceback
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.capture_cache_bindings import query_cache_binding
from cadence_mcp.capture_cache_replace import CaptureCacheReplacements
from cadence_mcp.capture_references import read_units
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process

class LostReceipt(CaptureCacheReplacements):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned receipt removed after save.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureCacheReplacements):
 def execute(self,d,p,cancel,on_started):
  def start(pid):
   on_started(pid);row=self._load(d.name.removeprefix('plan-'))[2]
   result=self.cancel(row['plan']['planId'],row['digest']);assert result['cancelRequested']
  return super().execute(d,p,cancel,start)
class CorruptUnrelated(CaptureCacheReplacements):
 def execute(self,d,p,cancel,on_started):
  process=super().execute(d,p,cancel,on_started);assert process['returnCode']==0
  cap=self.capture;sid=next(iter(cap.sessions));units=read_units(cap,sid);affected={r['nativeId'] for r in p['changes']}
  unit=next(u for u in units.values() if u['kind']=='placed' and u['nativeId'] not in affected)
  expected=json.loads(Path(p['expectedEvidence']).read_text(encoding='utf-8'));state=next(r for r in expected['state'] if r['nativeId']==unit['nativeId']);old=next(v['value'] for v in state['effective'] if v['name']=='Value')
  argv=[self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_property.tcl',self.config.install_root,d/'design.dsn',d/'unrelated-change.json',unit['partId'],'100000','Value',old,'CORRUPT_UNRELATED',unit['schematicName'],unit['pageName'],unit['reference']]
  second=run_owned_process(argv,d,process_env(self.config),60,cancel=cancel,on_started=on_started);assert second['returnCode']==0 and second['remainingOwnedProcesses']==0
  (d/'unrelated-process.json').write_text(json.dumps(second,indent=2),encoding='utf-8');return process

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root;prior=json.loads((fixture/'report.json').read_text(encoding='utf-8'));source=fixture/'source-with-overrides.dsn';library_path=Path(prior['cases'][0]['request']['newLib'])
details=json.loads((fixture/'packageName-1/expected-details.json').read_text(encoding='utf-8'));baseline=json.loads((fixture/'baseline/definition.json').read_text(encoding='utf-8'));oracle={}
for detail in details.values():
 g=detail['geometry'];ref=g['reference'];pins=[]
 for p in g['pins']:
  old=next(v for v in baseline['pin'] if v['reference']==ref and v['number']==p['number'])
  pins.append({k:p[k] for k in ('number','name','hotSpot')}|{'connected':old['connected'],'net':old['net'] if old['connected'] else None})
 oracle[ref]=pins
report={'passed':False,'sourceHashesBefore':{'design':sha256(source),'library':sha256(library_path)},'cases':[]}
modes=[('receipt_loss',LostReceipt,'receipt_lost_fixture'),('cancel_at_start',CancelAtStart,'operation_cancelled'),('native_timeout',CaptureCacheReplacements,'timeout'),('unrelated_instance_changed',CorruptUnrelated,'cache_instance_state_mismatch'),('changed_source',CaptureCacheReplacements,'target_changed'),('changed_library',CaptureCacheReplacements,'target_changed'),('changed_expectation',CaptureCacheReplacements,'target_changed')]
for mode,cls,code in modes:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  c=Config(a.install_root,root/mode,(fixture,library_path.parent),60);cap=CaptureService(c);libs=LibraryService(c);writer=cls(c,cap,libs)
  sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];lid=libs.open(str(library_path))['libraryId'];data=libs.sessions[lid]['data'];pkg=next(p for p in data['package'] if p['name']=='R');part=next(p for p in data['part'] if p['packageId']==pkg['objectId'])
  targets=[p for p in cap.sessions[sid]['data']['part'] if p['reference'] in oracle];target=next(p for p in targets if p['reference']=='R101')
  declarations=[{'partId':p['objectId'],'libraryPartId':part['objectId'],'pins':copy.deepcopy(oracle[p['reference']])} for p in targets]
  plan=writer.plan(sid,target['objectId'],lid,pkg['objectId'],declarations);row['plan']=plan;payload=writer._load(plan['planId'])[2]['plan']['payload']
  if mode=='native_timeout':writer.config=Config(a.install_root,root/mode,(fixture,library_path.parent),1)
  for m,key in [('changed_source','sourceDesign'),('changed_library','sourceLibrary'),('changed_expectation','expectedEvidence')]:
   if mode==m:
    file=Path(payload[key]);file.write_bytes(file.read_bytes()+b'owned frozen input tamper')
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as e:assert e.code==code,e.code;row['errorCode']=e.code
  else:raise AssertionError('Expected refusal absent')
  d,_,ledger=writer._load(plan['planId'])
  if mode.startswith('changed_'):assert ledger['state']=='planned' and not (d/'design.dsn').exists()
  else:
   row['process']=ledger['process'];assert row['process']['remainingOwnedProcesses']==0 and row['process']['rootExitSignalConfirmed'] and row['process']['observedProcessExitSignalsConfirmed']
   if mode=='native_timeout':assert row['process']['state']=='timeout'
   if mode=='receipt_loss':
    before=sha256(d/'design.dsn');lib_before=sha256(d/'library.olb');fresh=CaptureCacheReplacements(c,CaptureService(c),LibraryService(c));result=fresh.recover(plan['planId'],plan['planDigest'])
    assert result['state']=='verified_recovered' and result['nativeCompletionVerified'] is False and result['sourceQualifiedCacheGraphVerified']
    assert sha256(d/'design.dsn')==before and sha256(d/'library.olb')==lib_before;row['recovered']=result
   else:
    try:writer.open_output(plan['planId'],plan['planDigest'])
    except CadenceError as e:assert e.code=='output_unverified'
    else:raise AssertionError('Opened unverified output')
    try:writer.apply(plan['planId'],plan['planDigest'],mode)
    except CadenceError as e:assert e.code=='write_not_replayed'
    else:raise AssertionError('Replayed mutation')
  row['passed']=True
 except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashesAfter']={'design':sha256(source),'library':sha256(library_path)};report['passed']=all(r['passed'] for r in report['cases']) and report['sourceHashesBefore']==report['sourceHashesAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
