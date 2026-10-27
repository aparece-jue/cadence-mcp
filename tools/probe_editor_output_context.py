"""One dispatch of fixed editor adapter; preserve source and host, verify output."""
import json,shutil,time,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_jobs import acquire_guard
from cadence_mcp.native_host_fence import claim,release
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.gui_readiness import require_write_ready
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-output-context-20261027';root.mkdir(exist_ok=False)
fresh=r/'.local/editor-wire-fresh-binding-20261027';binding=fresh/json.loads((fresh/'report.json').read_text(encoding='utf-8'))['bindingRelativePath'];b=json.loads(binding.read_text(encoding='utf-8'))
hello=RpcConnection(binding).call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean';require_write_ready(b['expectedPid']);assert process_image(b['expectedPid'])==Path(b['expectedExecutable'])
source=Path(b['expectedDesign']);host_project=source.with_suffix('.opj');source_hash=sha256(source);project_hash=sha256(host_project)
assert source_hash=='8184f7f92848f536e9bc7a7969b5b597fe62515b1dfe5fef1bcb814b5e599397'
nonce=uuid.uuid4().hex;d=root/('plan-'+nonce);d.mkdir();target=d/'design.dsn';shutil.copy2(source,target)
project=d/'editor-output.opj';project.write_text('(ExpressProject "editor-output"\n (ProjectVersion "19981106")\n (SoftwareVersion "24.1")\n (ProjectType "PCB")\n (Folder "Design Resources" (Folder "Library") (NoModify) (File "./design.dsn" (Type "Schematic Design")))\n)\n',encoding='utf-8')
expected={'addedPath':[[100,600],[300,600]],'alias':'EDITOR_NATIVE','aliasLocation':[100,600],'preserveAllPriorWireNets':True};write_json(root/'expected.json',expected)
args=[str(b['expectedPid']),source.as_posix(),host_project.as_posix(),project.as_posix(),target.as_posix(),'ROOT','MAIN','100','600','300','600','EDITOR_NATIVE','100','600',(d/'native-result.json').as_posix(),(d/'entered.txt').as_posix(),nonce]
code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'editor_wire_add_job.tcl').as_posix())+'\n::cmcpEditorWire::run '+' '.join(tcl_string(a) for a in args)+'\n'
(d/'payload.tcl').write_text(code,encoding='utf-8');(d/'invoke.tcl').write_text('source '+tcl_string((d/'payload.tcl').as_posix())+'\n',encoding='utf-8')
owner={'kind':'native_netlist_v1','jobId':nonce,'pid':b['expectedPid'],'instanceId':b['instanceId'],'jobDirectory':str(d),'bindingSha256':sha256(binding)}
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,root),30)
report={'passed':False,'noReplay':True,'sourceBefore':source_hash,'hostProjectBefore':project_hash,'jobDirectory':d.relative_to(r).as_posix()};guard=acquire_guard(binding.parent)
try:
 claim(binding,owner);write_json(d/'dispatch-claim.json',owner)
 report['process']=run_owned_process([Path(b['expectedExecutable']),d/'invoke.tcl'],d,process_env(cfg),10)
 end=time.monotonic()+20
 while not (d/'native-result.json').exists() and time.monotonic()<end:time.sleep(.1)
 assert (d/'native-result.json').exists(),'native completion unknown; fence retained'
 receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));report['receipt']=receipt
 assert receipt['jobId']==nonce and receipt['pid']==b['expectedPid']
 if receipt['hostRestored']:release(binding,owner)
 assert receipt['saved'] and receipt['hostRestored'] and receipt['invocationReturned'],receipt
 after=RpcConnection(binding).call('hello',{});report['generationBefore']=hello['generation'];report['generationAfter']=after['generation']
 assert not after['data']['bindingLost'] and after['data']['dirtyState']=='clean' and after['generation']>hello['generation']
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(root/'connections.json'),'connections'],root)
 objects=json.loads((root/'connections.json').read_text(encoding='utf-8'))['objects'];wires=[w for w in objects if w['kind']=='wire'];aliases=[w for w in objects if w['kind']=='alias']
 prior=json.loads((r/'.local/placewire-junction-20261027/connections.json').read_text(encoding='utf-8'))['objects']
 def stable(items):return sorted((tuple(map(tuple,w['attributes']['points'])),w['attributes']['net']) for w in items if w['kind']=='wire')
 expected_wire={'kind':'wire','attributes':{'points':expected['addedPath'],'net':'EDITOR_NATIVE'}}
 assert stable(wires)==stable(prior+[expected_wire]),'wire geometry or untouched native net changed'
 assert len(aliases)==1 and aliases[0]['attributes']['name']=='EDITOR_NATIVE' and aliases[0]['attributes']['location']==[100,600]
 report['passed']=True
except BaseException as error:report['error']=str(error)
finally:
 guard.close();report['sourceUnchanged']=sha256(source)==source_hash;report['hostProjectUnchanged']=sha256(host_project)==project_hash
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged'];write_json(root/'report.json',report);print(json.dumps(report),flush=True)
