"""Development-only fixed-fixture runner. Not imported or exposed by MCP server."""
import json,shutil,time,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_jobs import acquire_guard
from cadence_mcp.gui_readiness import require_write_ready
from cadence_mcp.native_host_fence import claim,release,ensure_idle
from cadence_mcp.process_tree import run_owned_process

def run_fixed_probe(root,source,schematic,page,mutation,expected):
 r=Path(__file__).resolve().parents[1];root=root.resolve();source=source.resolve(strict=True)
 assert root.is_relative_to(r/'.local') and source.is_relative_to(r/'.local')
 root.mkdir(exist_ok=False);write_json(root/'expected.json',expected);source_before=sha256(source);oracle_before=sha256(root/'expected.json')
 fresh=r/'.local/editor-wire-fresh-binding-20261027';binding=fresh/json.loads((fresh/'report.json').read_text(encoding='utf-8'))['bindingRelativePath'];b=json.loads(binding.read_text(encoding='utf-8'));rpc=RpcConnection(binding);hello=rpc.call('hello',{})
 assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean';require_write_ready(b['expectedPid']);ensure_idle(binding);assert process_image(b['expectedPid'])==Path(b['expectedExecutable'])
 active=Path(b['expectedDesign']);host_project=active.with_suffix('.opj');active_before=sha256(active);project_before=sha256(host_project)
 nonce=uuid.uuid4().hex;d=root/('plan-'+nonce);d.mkdir();target=d/'design.dsn';shutil.copy2(source,target)
 project=d/'fixture.opj';project.write_text('(ExpressProject "fixture" (ProjectVersion "19981106") (SoftwareVersion "24.1") (ProjectType "PCB") (Folder "Design Resources" (Folder "Library") (File "./design.dsn" (Type "Schematic Design"))))\n',encoding='utf-8')
 template=ADAPTERS/'editor_wire_add_job.tcl';text=template.read_text(encoding='utf-8').replace('::cmcpEditorWire','::cmcpFixedFixture');start=text.index('   set phase place_wire');end=text.index('   set phase save',start);text=text[:start]+mutation+'\n'+text[end:];adapter=d/'fixed-fixture-adapter.tcl';adapter.write_text(text,encoding='utf-8')
 args=[b['expectedPid'],active.as_posix(),host_project.as_posix(),project.as_posix(),target.as_posix(),schematic,page,'',0,0,10,0,'UNUSED',0,0,(d/'native-result.json').as_posix(),(d/'entered.txt').as_posix(),nonce]
 code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string(adapter.as_posix())+'\n::cmcpFixedFixture::run '+' '.join(tcl_string(a) for a in args)+'\n';(d/'payload.tcl').write_text(code,encoding='utf-8');(d/'invoke.tcl').write_text('source '+tcl_string((d/'payload.tcl').as_posix())+'\n',encoding='utf-8')
 config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45);owner={'kind':'native_netlist_v1','jobId':nonce,'pid':b['expectedPid'],'instanceId':b['instanceId'],'jobDirectory':str(d),'bindingSha256':sha256(binding)}
 report={'nativeAccepted':False,'sourceBefore':source_before,'jobDirectory':d.relative_to(r).as_posix(),'templateSha256':sha256(template),'fixtureAdapterSha256':sha256(adapter),'oracleSha256':oracle_before,'noReplay':True};guard=acquire_guard(binding.parent)
 try:
  claim(binding,owner);write_json(d/'dispatch-claim.json',owner);report['process']=run_owned_process([Path(b['expectedExecutable']),d/'invoke.tcl'],d,process_env(config),10)
  until=time.monotonic()+30
  while not (d/'native-result.json').exists() and time.monotonic()<until:time.sleep(.1)
  assert (d/'native-result.json').exists(),'Unknown native outcome: fence retained, do not resend'
  receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));report['receipt']=receipt;assert receipt['jobId']==nonce and receipt['pid']==b['expectedPid']
  if receipt['hostRestored']:
   after=rpc.call('hello',{});assert not after['data']['bindingLost'] and after['data']['dirtyState']=='clean';assert sha256(active)==active_before and sha256(host_project)==project_before;release(binding,owner)
  assert receipt['saved'] and receipt['invocationReturned'] and receipt['hostRestored'],receipt
  assert not (d/'design.dsnlck').exists();report['nativeAccepted']=True
 except BaseException as error:report['error']=str(error)
 finally:
  guard.close();report['sourceUnchanged']=sha256(source)==source_before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle_before;report['hostUnchanged']=sha256(active)==active_before and sha256(host_project)==project_before;write_json(root/'dispatch-report.json',report)
 return config,d,report
