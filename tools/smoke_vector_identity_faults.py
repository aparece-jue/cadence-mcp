"""Pure graphic corruption must fail even when pin/net/pose/value checks pass."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.capture_place import CapturePlacements
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','baseline','vector-root','text-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);report={'passed':False,'scope':'owned post-save ellipse/font corruption, not source mutation','cases':[]}
for kind,directory in [('ellipse',a.vector_root/'ellipse'),('text',a.text_root/'text')]:
 directory=directory.resolve(strict=True);lib=directory/'library.olb';libhash=sha256(lib);d=root/kind;d.mkdir();cfg=Config(a.install_root,d/'work',(source.parent,lib.parent),60);cap=CaptureService(cfg);library=LibraryService(cfg);row={'case':kind,'passed':False};report['cases'].append(row)
 try:
  sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];data=cap.sessions[sid]['data'];page=next(p for p in data['page'] if p['name']=='MCP_PLACE');lid=library.open(str(lib))['libraryId'];ld=library.sessions[lid]['data'];device=next(v for v in ld['device'] if v['designator']=='A');part=next(p for p in ld['part'] if p['deviceId']==device['objectId'] and p['name'].endswith('.Normal'));spec=json.loads((directory/'spec.json').read_text(encoding='utf-8'));dev=next(v for v in spec['devices'] if v['designator']=='A');symbol=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.Normal'));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[700+p['hotSpot'][0],300+p['hotSpot'][1]],'connected':False,'net':None} for p in symbol['pins']];base=json.loads(a.baseline.read_text(encoding='utf-8'));pid=next(p['objectId'] for p in base['page'] if p['name']=='MCP_PLACE');existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':p['reference'],'pinNumber':p['number'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in base['pin'] if p['pageId']==pid];writer=CapturePlacements(cfg,cap,library);plan=writer.plan(sid,page['objectId'],lid,part['objectId'],'U901',[700,300],0,0,'VECTOR',pins,existing);row['plan']=plan;execute=writer.execute
  def corrupt(job,payload,cancel,started):
   process=execute(job,payload,cancel,started);assert process['returnCode']==0;original=sha256(job/'design.dsn');write_json(job/'graphic-poison.json',{'kind':kind,'schematicName':payload['schematicName'],'pageName':payload['pageName'],'reference':payload['reference']});poison=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'poison_placed_vector.tcl'),str(cfg.install_root),str(job/'design.dsn'),str(job/'graphic-poison.json'),str(job/'poison-receipt.json')],job,process_env(cfg),60);assert poison['returnCode']==0 and poison['remainingOwnedProcesses']==0 and json.loads((job/'poison-receipt.json').read_text())['saved'];assert sha256(job/'design.dsn')!=original;row['poisonProcess']=poison;return process
  writer.execute=corrupt
  try:writer.apply(plan['planId'],plan['planDigest'],'corrupt-vector');raise AssertionError('Pure vector corruption accepted')
  except CadenceError as e:assert e.code=='placement_view_mismatch',(e.code,str(e));row['expectedError']=e.code
  job,_,ledger=writer._load(plan['planId']);row['comparison']=json.loads((job/'verified-view.json').read_text(encoding='utf-8'));assert row['comparison']['matches'] is False
  try:writer.open_output(plan['planId'],plan['planDigest']);raise AssertionError('Corrupt output opened')
  except CadenceError as e:assert e.code=='output_unverified'
  try:writer.apply(plan['planId'],plan['planDigest'],'corrupt-vector');raise AssertionError('Corrupt mutation replayed')
  except CadenceError as e:assert e.code=='write_not_replayed'
  row['sourceAndLibraryUnchanged']=sha256(source)==before and sha256(lib)==libhash;row['passed']=row['sourceAndLibraryUnchanged'] and ledger['process']['remainingOwnedProcesses']==0
 except BaseException as e:
  import traceback
  row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(kind,row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
