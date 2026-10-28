"""Native moved-triangle source with frozen mathematical contact expectations."""
import asyncio,json,os,shutil,sys,traceback
from pathlib import Path
from collections import Counter
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/symbol-contacts-mcp-20261028';root.mkdir(exist_ok=False)
source=r/'.local/noncentered-pose-rectangle-a-20261026/r0-m0/design.dsn';source_before=sha256(source)
expected={'partId':'schematic-1/page-1/part-1','pageId':'schematic-1/page-1','baselineLocation':[600,400],'baselineContacts':0,'movedLocation':[330,300],'movedContactMultiset':[{'point':[350,310],'kind':'crossing','count':2},{'point':[350,330],'kind':'t_contact','count':2},{'point':[330,310],'kind':'crossing','count':1}],'samePageWireSegments':15,'otherPageMustNotContribute':True,'localTriangle':[[[0,0],[40,20]],[[40,20],[0,40]],[[0,40],[0,0]]]}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'native-work',(source.parent,),45)
target=root/'moved.dsn';shutil.copy2(source,target)
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',r/'tools/fixture_part_pose.tcl',cfg.install_root,target,root/'pose.json',expected['partId'],'100000','0','0','330','300'],root,process_env(cfg),45)
assert process['returnCode']==0 and process['remainingOwnedProcesses']==0,process
for name,path in [('before',source),('after',target)]:run_tcl(cfg,'inspect_geometry.tcl',[str(path),str(root/(name+'-wires.json')),'100000'],root)
before=json.loads((root/'before-wires.json').read_text(encoding='utf-8'));after=json.loads((root/'after-wires.json').read_text(encoding='utf-8'))
assert before==after,'Fixture move changed existing wire geometry or native net identities'
saved=sha256(target)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(root/'work'),'--read-root',str(r/'.local'),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fixtureProcess':process,'fullV02Accepted':False,'renderedClearanceAccepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools);assert len(tools)==223
   async def call(name,args,error=None):
    result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content)
    if error:assert result.is_error and result.structured_content['error']['code']==error,result
    else:assert not result.is_error,result
    return result.structured_content.get('data')
   wanted=Counter({(tuple(x['point']),x['kind']):x['count'] for x in expected['movedContactMultiset']})
   for name,path,want in [('baseline',source,Counter()),('moved',target,wanted)]:
    ws=await call('cadence_create_workspace',{'sourceDesign':str(path)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    args={'sessionId':sid,'partId':expected['partId']};result=await call('capture_check_symbol_contacts',args)
    assert result['linearBoundarySegmentsChecked']==3 and result['wireSegmentsChecked']==15 and result['linearBoundaryCoverageComplete']
    assert result['designPassed'] is None and not result['renderedClearanceVerified'] and not result['electricalConnectivityVerified']
    actual=Counter((tuple(f['point']),f['contactKind']) for f in result['findings']);assert actual==want,(name,actual,want)
    wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':expected['pageId'],'limit':1000}))['items'];ids={w['objectId'] for w in wires}
    assert all(f['wireId'] in ids and f['pageId']==expected['pageId'] and f['partId']==expected['partId'] for f in result['findings'])
    artifact=root/'work'/ws['workspaceId']/result['artifact']['workspaceRelativePath'];assert sha256(artifact)==result['artifact']['sha256']
    report['cases'].append({'name':name,'passed':True,'result':result})
    await call('capture_check_symbol_contacts',{'sessionId':sid,'partId':'schematic-1/page-1/part-999'},'object_not_found')
    if name=='moved':
     (root/'work'/ws['workspaceId']/'design.dsn').write_bytes(b'owned stale design negative')
     await call('capture_check_symbol_contacts',args,'target_changed')
    await call('capture_close',{'sessionId':sid});await call('capture_check_symbol_contacts',args,'session_lost')
   mixed=json.loads((r/'.local/mixed-part-vectors-mcp-v2-20261028/expected.json').read_text(encoding='utf-8'))['cases'][0]
   ws=await call('cadence_create_workspace',{'sourceDesign':mixed['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   result=await call('capture_check_symbol_contacts',{'sessionId':sid,'partId':'schematic-1/page-2/part-1'})
   assert not result['linearBoundaryCoverageComplete'] and len(result['skippedVectors'])==5 and result['designPassed'] is None
   report['mixedUnsupportedResult']=result;await call('capture_close',{'sessionId':sid})
   report.update(passed=True,fiveNativeContactsAccepted=True,baselineNoContactAccepted=True,crossPageIsolationAccepted=True,unknownGeometryExplicit=True,artifactHashVerified=True,staleAndClosedSessionRefused=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==source_before and sha256(target)==saved;report['oracleUnchanged']=sha256(root/'expected.json')==oracle
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
