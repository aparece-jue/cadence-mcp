"""Actual MCP verifies page IDs fence identical-coordinate native wires."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from collections import Counter
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];native=r/'.local/native-wire-page-isolation-20261027'
prior=json.loads((native/'report.json').read_text(encoding='utf-8'));assert prior['passed']
source=Path(prior['target']);oracle=native/'expected.json';oracle_hash=sha256(oracle)
root=r/'.local/wire-page-isolation-mcp-20261027';root.mkdir(exist_ok=False)
expected={'wireCount':6,'segmentCount':6,'vertexCount':12,'countsByRule':{'WIRE-NON-ORTHOGONAL':2,'WIRE-CROSSING-CANDIDATE':2},'crossingPoint':[150,500],'pages':['MAIN','CHILD_PAGE'],'falseCrossPagePoint':[150,150]}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceBefore':sha256(source),'oracleSha256':oracle_hash,'fullV02Accepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args,error=None):
    result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content)
    if error:assert result.is_error and result.structured_content['error']['code']==error,result
    else:assert not result.is_error,result
    return result.structured_content.get('data')
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
   opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items']
   names={p['objectId']:p['name'] for p in pages};assert set(names.values())==set(expected['pages'])
   report['pages']=pages
   wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items']
   assert len(wires)==6;owners={w['objectId']:w['pageId'] for w in wires}
   base=await call('capture_check_wiring',{'sessionId':sid});report['base']=base
   for key in ('wireCount','segmentCount','vertexCount','countsByRule'):assert base[key]==expected[key],(key,base[key])
   counts=Counter()
   for finding in base['findings']:
    page=finding['pageId'];assert page in names
    for ref in finding['objects']:assert owners[ref['objectId']]==page,'cross_page_object_reference'
    if finding['ruleId']=='WIRE-CROSSING-CANDIDATE':
     assert finding['point']==expected['crossingPoint'];counts[names[page]]+=1
   assert dict(counts)=={'MAIN':1,'CHILD_PAGE':1},counts
   assert base['geometryComplete'] and not base['electricalConnectivityVerified'] and base['designPassed'] is None
   artifact=root/'work'/ws['workspaceId']/base['artifact']['workspaceRelativePath'];assert sha256(artifact)==base['artifact']['sha256']
   # Native off-grid counts remain page-specific even at identical coordinates.
   grid=await call('capture_check_wiring',{'sessionId':sid,'gridSize':10,'gridOrigin':[5,5]});report['grid']=grid
   off=[f for f in grid['findings'] if f['ruleId']=='WIRE-OFF-GRID-VERTEX'];assert Counter(names[f['pageId']] for f in off)=={'MAIN':6,'CHILD_PAGE':6}
   await call('capture_close',{'sessionId':sid})
   await call('capture_check_wiring',{'sessionId':sid},'session_lost')
   report.update(passed=True,oneCrossingPerPage=True,crossPageDiagonalNotReported=True,allFindingObjectOwnersMatch=True,gridPageIsolationAccepted=True,closedSessionRefused=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==report['sourceBefore'];report['oracleUnchanged']=sha256(oracle)==oracle_hash and sha256(root/'expected.json')==expected_hash
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
