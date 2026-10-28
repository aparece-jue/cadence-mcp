"""Real native closed-outline containment without boundary crossings."""
import asyncio,json,os,shutil,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/closed-outline-mcp-20261028';root.mkdir(exist_ok=False)
source=r/'.local/noncentered-pose-rectangle-a-20261026/r0-m0/design.dsn';source_hash=sha256(source)
expected={'partId':'schematic-1/page-1/part-1','closedLocalBox':[0,0,100,100],'inside':{'location':[600,350],'containments':1,'wireStart':[640,380],'wireEnd':[660,380]},'outside':{'location':[700,350],'containments':0},'boundaryContacts':0,'samePageWireSegments':15}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
template=(r/'tools/fixture_part_pose.tcl').read_text(encoding='utf-8').replace('source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]','source '+tcl_string((ADAPTERS/'json.tcl').as_posix()))
anchor='                            cmcp::check [$p MarkModified]'
assert template.count(anchor)==1
mutation='''                            set ds [DboState];set definition [$part GetDefiningPart $ds];cmcp::check $ds
                            if {$definition eq "NULL"} {error no_defining_part}
                            set bs [DboState];set outline [$definition NewBox $bs [DboTclHelper_sMakeCPoint 0 0] [DboTclHelper_sMakeCPoint 100 100] 0 0 0 0];cmcp::check $bs
                            if {$outline eq "NULL"} {error no_closed_outline}
'''
adapter=root/'fixture-closed-outline.tcl';adapter.write_text(template.replace(anchor,mutation+anchor),encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'native-work',(source.parent,),45)
run_tcl(cfg,'inspect_geometry.tcl',[str(source),str(root/'source-wires.json'),'100000'],root);before=json.loads((root/'source-wires.json').read_text(encoding='utf-8'))
prepared=[]
for name in ('outside','inside'):
 d=root/name;d.mkdir();target=d/'design.dsn';shutil.copy2(source,target);x,y=expected[name]['location']
 child=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',adapter,cfg.install_root,target,d/'fixture-receipt.json',expected['partId'],'100000','0','0',str(x),str(y)],d,process_env(cfg),45)
 assert child['returnCode']==0 and child['remainingOwnedProcesses']==0,child
 run_tcl(cfg,'inspect_geometry.tcl',[str(target),str(d/'wires.json'),'100000'],d)
 assert json.loads((d/'wires.json').read_text(encoding='utf-8'))==before,'Original wire geometry/native net identity changed'
 prepared.append({'name':name,'source':str(target),'sha256':sha256(target),'fixtureProcess':child})
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fullV02Accepted':False,'renderedClearanceAccepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content);assert not value.is_error,value
    return value.structured_content['data']
   for case in prepared:
    ws=await call('cadence_create_workspace',{'sourceDesign':case['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    vectors=await call('capture_query_part_vectors',{'sessionId':sid,'partId':expected['partId'],'limit':1000});assert vectors['total']==4
    boxes=[v for v in vectors['items'] if v['kind']=='box'];assert len(boxes)==1 and boxes[0]['localDescriptor']==['box',[0,0,100,100],0,0,0,0]
    x,y=expected[case['name']]['location'];assert boxes[0]['pageControlPoints']==[[x,y],[x+100,y],[x+100,y+100],[x,y+100]]
    result=await call('capture_check_symbol_contacts',{'sessionId':sid,'partId':expected['partId']});assert result['profile']=='symbol-wire-linear-contacts@0.2.0'
    assert result['simpleClosedOutlinesChecked']==1 and result['skippedContainmentOutlines']==[] and result['wireSegmentsChecked']==15
    assert len(result['findings'])==expected[case['name']]['containments'],(case,result)
    assert result['designPassed'] is None and not result['renderedClearanceVerified']
    for f in result['findings']:
     assert f['contactKind']=='contained_segment' and f['vectorSegmentIndex'] is None and f['vectorId']==boxes[0]['objectId']
     assert f['wireStart']==expected['inside']['wireStart'] and f['wireEnd']==expected['inside']['wireEnd']
    artifact=root/'work'/ws['workspaceId']/result['artifact']['workspaceRelativePath'];assert sha256(artifact)==result['artifact']['sha256']
    report['cases'].append({**case,'result':result,'passed':True});await call('capture_close',{'sessionId':sid})
   report.update(passed=True,nativeInsideWithoutBoundaryCrossingAccepted=True,nativeOutsideControlAccepted=True,originalWireMapPreserved=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourcesUnchanged']=sha256(source)==source_hash and all(sha256(Path(c['source']))==c['sha256'] for c in prepared)
 report['oracleUnchanged']=sha256(root/'expected.json')==oracle
 report['passed']=report['passed'] and report['sourcesUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
