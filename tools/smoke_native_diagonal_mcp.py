"""Real stdio MCP acceptance against a predeclared native diagonal matrix."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

r=Path(__file__).resolve().parents[1];native=r/'.local/native-diagonal-20261027'
prior=json.loads((native/'report.json').read_text(encoding='utf-8'));assert prior['passed']
source=Path(prior['target']);oracle=native/'expected.json';oracle_before=sha256(oracle)
root=r/'.local/native-diagonal-mcp-20261027';root.mkdir(exist_ok=False)
expected={'wireCount':10,'segmentCount':10,'vertexCount':20,
 'countsByRule':{'WIRE-NON-ORTHOGONAL':9,'WIRE-CROSSING-CANDIDATE':1,'WIRE-COLLINEAR-OVERLAP':1,'WIRE-T-CONTACT-CANDIDATE':1},
 'crossingExact':[{'numerator':820,'denominator':7},{'numerator':760,'denominator':7}],
 'overlap':[[325,125],[375,175]],'tContact':[550,150],
 'grids':[{'size':10,'origin':[0,0],'offGrid':2},{'size':10,'origin':[5,5],'offGrid':18},{'size':5,'origin':[0,0],'offGrid':0}]}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceBefore':sha256(source),'oracleSha256':oracle_before,'fullV02Accepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content)
    assert not result.is_error,result;return result.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
   session=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=session['sessionId']
   base=await call('capture_check_wiring',{'sessionId':sid});report['base']=base
   for key in ('wireCount','segmentCount','vertexCount','countsByRule'):assert base[key]==expected[key],(key,base[key],expected[key])
   assert base['geometryComplete'] and base['designPassed'] is None and not base['electricalConnectivityVerified']
   findings=base['findings']
   cross=[f for f in findings if f['ruleId']=='WIRE-CROSSING-CANDIDATE'][0]
   assert cross['point'] is None and cross['pointExact']==expected['crossingExact'],cross
   overlap=[f for f in findings if f['ruleId']=='WIRE-COLLINEAR-OVERLAP'][0]
   assert sorted([overlap['start'],overlap['end']])==expected['overlap'],overlap
   contact=[f for f in findings if f['ruleId']=='WIRE-T-CONTACT-CANDIDATE'][0];assert contact['point']==expected['tContact']
   # Exact finding counts also reject false contacts at shared ends or the gap.
   report['gridResults']=[]
   for grid in expected['grids']:
    result=await call('capture_check_wiring',{'sessionId':sid,'gridSize':grid['size'],'gridOrigin':grid['origin']})
    assert result['countsByRule'].get('WIRE-OFF-GRID-VERTEX',0)==grid['offGrid']
    for key,value in expected['countsByRule'].items():assert result['countsByRule'][key]==value
    report['gridResults'].append(result)
   for result in [base,*report['gridResults']]:
    artifact=root/'work'/ws['workspaceId']/result['artifact']['workspaceRelativePath']
    assert sha256(artifact)==result['artifact']['sha256']
   await call('capture_close',{'sessionId':sid})
   report.update(passed=True,exactRationalCrossing=True,reversedOverlap=True,tContact=True,endpointAndGapNegatives=True,threeNativeGrids=True,artifactHashesVerified=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==report['sourceBefore'];report['oracleUnchanged']=sha256(oracle)==oracle_before and sha256(root/'expected.json')==expected_hash
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error','sourceUnchanged','oracleUnchanged')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
