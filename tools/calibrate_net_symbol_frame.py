"""Independent source-box coordinate model, validated by native electrical attachment."""
import json,shutil,time,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_jobs import acquire_guard
from cadence_mcp.gui_readiness import require_write_ready
from cadence_mcp.native_host_fence import claim,release,ensure_idle
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_wire import point_on_path
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/c04-editor-matrix-base-20261027';root=r/'.local/net-symbol-frame-calibration-20261027';root.mkdir(exist_ok=False)
original=json.loads((base/'expected.json').read_text(encoding='utf-8'));source=base/'design.dsn';source_before=sha256(source)
# Only independent OLB definitions are inputs to the model. No instance values.
definitions=json.loads((base/'coordinate-frame.json').read_text(encoding='utf-8'))['definitions'];by_kind={d['kind']:d for d in definitions}
assert by_kind['global']['bounds']==[0,0,20,10] and by_kind['global']['pins']==[[10,10]]
assert by_kind['offpage']['bounds']==[0,0,10,20] and by_kind['offpage']['pins']==[[0,10]]
def transform(p,rotation,mirror):
 x,y=p
 if mirror:x=-x
 return ((x,y),(y,-x),(-x,-y),(-y,x))[rotation]
def model(attr,kind):
 d=by_kind[kind];left,top,right,bottom=d['bounds'];rotation=attr['rotationCode'];mirror=attr['mirrorCode'];corners=[transform((x,y),rotation,mirror) for x in (left,right) for y in (top,bottom)]
 x,y=transform(d['pins'][0],rotation,mirror);loc=attr['location'];return [loc[0]+x-min(p[0] for p in corners),loc[1]+y-min(p[1] for p in corners)]
predicted={};probes=[]
for page in ('PAGE_A','PAGE_B'):
 for obj in original['objects']:
  if obj['pageName']!=page or obj['kind'] not in by_kind:continue
  attr=obj['attributes'];predicted[(page,obj['kind'],tuple(attr['location']))]=model(attr,obj['kind'])
 for obj in original['objects']:
  if obj['pageName']!=page or obj['kind'] not in by_kind:continue
  attr=obj['attributes'];good=model(attr,obj['kind']);old=attr['hotSpot']
  if page=='PAGE_B' and good==old:continue
  start=good if page=='PAGE_A' else old
  all_good=[value for (p,k,loc),value in predicted.items() if p==page]
  ends=([start[0]+30,start[1]],[start[0]-30,start[1]],[start[0],start[1]+30],[start[0],start[1]-30])
  end=next(end for end in ends if not any(point_on_path(point,[start,end]) for point in all_good if page=='PAGE_B' or point!=good))
  probes.append({'page':page,'kind':obj['kind'],'origin':attr['location'],'rotation':attr['rotationCode'],'mirror':attr['mirrorCode'],'points':[start,end],'mustAttach':page=='PAGE_A','expectedName':'DUP_SUPPLY' if obj['kind']=='global' else 'DUP_LINK'})
oracle={'model':'mirror-X and clockwise rotate source pin and all four source-box corners, then rebase transformed box minimum to instance location','definitionsFromIndependentOlb':definitions,'targetReadoutsUsedToBuildOracle':False,'probes':probes}
write_json(root/'expected.json',oracle);oracle_hash=sha256(root/'expected.json');assert sum(p['mustAttach'] for p in probes)==16 and len(probes)==28
fresh=r/'.local/editor-wire-fresh-binding-20261027';binding=fresh/json.loads((fresh/'report.json').read_text(encoding='utf-8'))['bindingRelativePath'];b=json.loads(binding.read_text(encoding='utf-8'));hello=RpcConnection(binding).call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean';require_write_ready(b['expectedPid']);ensure_idle(binding)
active=Path(b['expectedDesign']);host_project=active.with_suffix('.opj');host_before=sha256(active);project_before=sha256(host_project);assert process_image(b['expectedPid'])==Path(b['expectedExecutable'])
nonce=uuid.uuid4().hex;d=root/('plan-'+nonce);d.mkdir();target=d/'design.dsn';shutil.copy2(source,target)
project=d/'calibration.opj';project.write_text('(ExpressProject "calibration" (ProjectVersion "19981106") (SoftwareVersion "24.1") (ProjectType "PCB") (Folder "Design Resources" (Folder "Library") (File "./design.dsn" (Type "Schematic Design"))))\n',encoding='utf-8')
adapter=(ADAPTERS/'editor_wire_add_job.tcl').read_text(encoding='utf-8').replace('::cmcpEditorWire','::cmcpFrameCalibration');start=adapter.index('   set phase place_wire');end=adapter.index('   set phase save',start);lines=['   set session $::DboSession_s_pDboSession;DboSession -this $session']
for page in ('PAGE_A','PAGE_B'):
 lines+=['   OPage TOP '+page,'   set st [DboState];set p [$s GetPage [DboTclHelper_sMakeCString '+page+'] $st];ck $st','   if {[GetActivePage] ne $p} {error wrong_calibration_page}']
 for probe in (p for p in probes if p['page']==page):lines+=['   PlaceWire '+' '.join(str(v/100) for pt in probe['points'] for v in pt),'   EndPlace']
 lines+=['   ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p]']
adapter=adapter[:start]+'\n'.join(lines)+'\n'+adapter[end:];(d/'calibration-adapter.tcl').write_text(adapter,encoding='utf-8')
args=[b['expectedPid'],active.as_posix(),host_project.as_posix(),project.as_posix(),target.as_posix(),'TOP','PAGE_A','',0,0,10,0,'UNUSED',0,0,(d/'native-result.json').as_posix(),(d/'entered.txt').as_posix(),nonce]
code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((d/'calibration-adapter.tcl').as_posix())+'\n::cmcpFrameCalibration::run '+' '.join(tcl_string(a) for a in args)+'\n';(d/'payload.tcl').write_text(code,encoding='utf-8');(d/'invoke.tcl').write_text('source '+tcl_string((d/'payload.tcl').as_posix())+'\n',encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45);owner={'kind':'native_netlist_v1','jobId':nonce,'pid':b['expectedPid'],'instanceId':b['instanceId'],'jobDirectory':str(d),'bindingSha256':sha256(binding)};report={'passed':False,'sourceBefore':source_before,'oracleSha256':oracle_hash,'jobDirectory':d.relative_to(r).as_posix()};guard=acquire_guard(binding.parent)
try:
 claim(binding,owner);write_json(d/'dispatch-claim.json',owner);report['process']=run_owned_process([Path(b['expectedExecutable']),d/'invoke.tcl'],d,process_env(cfg),10)
 until=time.monotonic()+30
 while not (d/'native-result.json').exists() and time.monotonic()<until:time.sleep(.1)
 assert (d/'native-result.json').exists(),'Unknown outcome; fence retained, never resend'
 receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));report['receipt']=receipt;assert receipt['jobId']==nonce and receipt['pid']==b['expectedPid']
 if receipt['hostRestored']:release(binding,owner)
 assert receipt['saved'] and receipt['invocationReturned'] and receipt['hostRestored'],receipt
 after=sha256(target);run_tcl(cfg,'inspect_net_symbol_bindings.tcl',[str(target),str(root/'bindings.json')],root);rows=json.loads((root/'bindings.json').read_text(encoding='utf-8'));checks=[]
 for probe in probes:
  wires=[row for row in rows if row['kind']=='wire' and row['pageName']==probe['page'] and sorted(row['points'])==sorted(probe['points'])];assert len(wires)==1
  group=wires[0]['group'];symbols=[row for row in rows if row['kind']==probe['kind'] and row['pageName']==probe['page'] and row['name']==probe['expectedName']]
  attached=group is not None and any(row['group']==group for row in symbols)
  checks.append({**probe,'attached':attached,'passed':attached==probe['mustAttach']})
 report['checks']=checks;assert all(c['passed'] for c in checks),'source-box attachment model or old-hypothesis nonattachment contradicted'
 assert sha256(target)==after;report.update(passed=True,positiveAttachments=16,negativeOldHypothesisPoints=12,independentNewProcessReopen=True)
except BaseException as error:report.update(error=str(error),errorCode=getattr(error,'code',None))
finally:
 guard.close();report['sourceUnchanged']=sha256(source)==source_before;report['hostUnchanged']=sha256(active)==host_before and sha256(host_project)==project_before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostUnchanged'] and report['oracleUnchanged'];write_json(root/'report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='checks'}),flush=True)
