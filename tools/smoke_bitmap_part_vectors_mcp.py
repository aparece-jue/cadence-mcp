"""Actual placed bitmap vectors against original frozen BMP/DIB expectations."""
import asyncio,hashlib,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];prior_root=r/'.local/created-bitmap-placement-20261024';prior=json.loads((prior_root/'report.json').read_text(encoding='utf-8'));assert prior['passed']
old_oracle=r/'.local/bitmap-public-creation-20261024/expected.json';old=json.loads(old_oracle.read_text(encoding='utf-8'));old_hash=sha256(old_oracle)
root=r/'.local/bitmap-part-vectors-mcp-20261028';root.mkdir(exist_ok=False)
cases=[]
for previous in prior['cases']:
 group='rgb24' if previous['case'].startswith('canonical') else 'rgb32';declaration=next(x for x in old if x['name']==group)
 name=previous['plan']['preview']['partName'];want=next(x for x in declaration['expected'] if x['partName']==name)['descriptor']
 bmp=Path(declaration['source']);blob=bmp.read_bytes();assert blob[:2]==b'BM' and hashlib.sha256(blob[14:]).hexdigest()==want[-1] and len(blob[14:])==want[-2]
 source=prior_root/'work'/previous['result']['outputWorkspaceRelativePath']/'design.dsn';assert sha256(source)==previous['result']['artifact']['sha256']
 bounds=want[1];x,y,xx,yy=bounds;points=[want[2],[x,y],[xx,y],[xx,yy],[x,yy]]
 cases.append({'name':previous['case'],'source':str(source),'sourceSha256':sha256(source),'reference':previous['plan']['preview']['reference'],'descriptor':want,'pagePoints':[[700+p[0],300+p[1]] for p in points],'bmp':str(bmp),'bmpSha256':sha256(bmp)})
(root/'expected.json').write_text(json.dumps({'originalOracleSha256':old_hash,'cases':cases},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(prior_root/'work'),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fullV02Accepted':False,'renderedClearanceAccepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content);assert not value.is_error,value
    return value.structured_content['data']
   for case in cases:
    ws=await call('cadence_create_workspace',{'sourceDesign':case['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'reference':case['reference'],'limit':1000}))['items'];assert len(parts)==1
    result=await call('capture_query_part_vectors',{'sessionId':sid,'partId':parts[0]['objectId'],'limit':1000})
    assert result['total']==14 and result['unsupportedCount']==1
    bitmaps=[v for v in result['items'] if v['kind']=='bitmap'];assert len(bitmaps)==1;bitmap=bitmaps[0]
    assert bitmap['localDescriptor']==case['descriptor'],(case['name'],bitmap)
    assert bitmap['pageControlPoints']==case['pagePoints']
    assert bitmap['nativeId'] is None and bitmap['rotationCode']==0 and bitmap['mirrorCode']==0
    report['cases'].append({'name':case['name'],'passed':True,'bitmap':bitmap,'sourceBmpDibBytesIndependentlyMatched':True})
    await call('capture_close',{'sessionId':sid})
   assert len({c['bitmap']['localDescriptor'][-1] for c in report['cases']})==2
   report.update(passed=True,fourPlacedBitmapCasesAccepted=True,independentBmpDibIdentityAccepted=True,distinctBitmapPayloadsPreserved=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourcesUnchanged']=all(sha256(Path(c['source']))==c['sourceSha256'] and sha256(Path(c['bmp']))==c['bmpSha256'] for c in cases)
 report['oracleUnchanged']=sha256(root/'expected.json')==oracle and sha256(old_oracle)==old_hash
 report['passed']=report['passed'] and report['sourcesUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
