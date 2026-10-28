"""Independent source-spec oracle for mixed defining vectors in placed native DSNs."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];prior_root=r/'.local/public-vector-placement-20261024'
prior=json.loads((prior_root/'report.json').read_text(encoding='utf-8'));assert prior['passed']
spec_path=r/'.local/public-vector-placement-fixture-20261024/spec.json';spec=json.loads(spec_path.read_text(encoding='utf-8'))
root=r/'.local/mixed-part-vectors-mcp-20261028';root.mkdir(exist_ok=False)
def descriptor(v):
 k=v['kind']
 if k=='line':return [k,v['start'],v['end'],v['style'],v['width']]
 if k in ('box','ellipse'):return [k,v['bounds'],v['style'],v['width'],v['fill'],v['hatch']]
 if k=='arc':return [k,v['bounds'],v['start'],v['end'],v['style'],v['width']]
 if k in ('polygon','polyline','bezier'):return [k,v['points'],v['style'],v['width']]+([v['fill'],v['hatch']] if k=='polygon' else [])
 if k=='text':return [k,v['text'],v['location'],v['bounds'],v['font'],0]
 raise ValueError(k)
def points(v):
 def corners(b):
  x,y,xx,yy=b;return [[x,y],[xx,y],[xx,yy],[x,yy]]
 if v['kind']=='line':return [v['start'],v['end']]
 if v['kind'] in ('box','ellipse'):return corners(v['bounds'])
 if v['kind']=='arc':return corners(v['bounds'])+[v['start'],v['end']]
 if v['kind'] in ('polygon','polyline','bezier'):return v['points']
 if v['kind']=='text':return [v['location']]+corners(v['bounds'])
 raise ValueError(v['kind'])
cases=[]
for old in prior['cases']:
 preview=old['plan']['preview'];symbol=next(s for s in spec['symbols'] if s['partName']==preview['partName'])
 source=prior_root/'work'/old['result']['outputWorkspaceRelativePath']/'design.dsn';assert sha256(source)==old['result']['artifact']['sha256']
 vectors=[dict(kind='line',**v) for v in symbol['lines']]+symbol['vectors'];expected=[]
 for v in vectors:
  if v['kind']=='fill':continue
  expected.append({'descriptor':descriptor(v),'pagePoints':[[700+p[0],300+p[1]] for p in points(v)]})
 cases.append({'name':old['case'],'source':str(source),'sourceSha256':sha256(source),'reference':preview['reference'],'expected':expected,'unsupportedFillCount':1,'total':len(vectors)})
(root/'expected.json').write_text(json.dumps({'sourceSpecSha256':sha256(spec_path),'cases':cases},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(prior_root/'work'),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fullV02Accepted':False,'renderedClearanceAccepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content);assert not result.is_error,result
    return result.structured_content['data']
   for case in cases:
    ws=await call('cadence_create_workspace',{'sourceDesign':case['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'reference':case['reference'],'limit':1000}))['items'];assert len(parts)==1
    args={'sessionId':sid,'partId':parts[0]['objectId'],'limit':2};rows=[];cursor=None
    while True:
     result=await call('capture_query_part_vectors',{**args,'cursor':cursor});rows+=result['items'];cursor=result['nextCursor']
     if cursor is None:break
    assert result['total']==case['total'] and len(rows)==case['total'] and result['unsupportedCount']==case['unsupportedFillCount'] and not result['supportedGeometryComplete']
    actual=[]
    for row in rows:
     assert row['nativeId'] is None and row['location']==[700,300] and row['rotationCode']==0 and row['mirrorCode']==0
     if row['kind']=='unsupported':assert row['localDescriptor'] is None and row['pageControlPoints']==[];continue
     actual.append({'descriptor':row['localDescriptor'],'pagePoints':row['pageControlPoints']})
    key=lambda x:json.dumps(x,sort_keys=True)
    assert sorted(actual,key=key)==sorted(case['expected'],key=key),(case['name'],actual,case['expected'])
    again=await call('capture_query_part_vectors',{'sessionId':sid,'partId':parts[0]['objectId'],'limit':1000});assert again['items']==rows
    assert [row['index'] for row in rows]==list(range(len(rows)))
    report['cases'].append({'name':case['name'],'passed':True,'rows':rows,'stableNativeOrderAcrossPaging':True})
    await call('capture_close',{'sessionId':sid})
   report.update(passed=True,sourceSpecGeometryAndStylesAccepted=True,textFontAndMultilineAccepted=True,eightSupportedKindsAndExplicitFillUnsupported=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourcesUnchanged']=all(sha256(Path(c['source']))==c['sourceSha256'] for c in cases)
 report['oracleUnchanged']=sha256(root/'expected.json')==oracle and sha256(spec_path)==json.loads((root/'expected.json').read_text(encoding='utf-8'))['sourceSpecSha256']
 report['passed']=report['passed'] and report['sourcesUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
