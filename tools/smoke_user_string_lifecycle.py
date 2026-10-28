"""Property-only set/delete and fresh-server recovery after explicit package marking."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];previous=r/'.local/native-user-string-contract-v2-20261028';proof=json.loads((previous/'report.json').read_text(encoding='utf-8'));assert proof['passed']
source=previous/'work'/proof['result']['outputWorkspaceRelativePath']/'library.olb';source_hash=sha256(source)
root=r/'.local/user-string-lifecycle-20261028';root.mkdir(exist_ok=False)
expected={p['name']:p for p in proof['after']['properties']['userProperties']}
cases=[{'name':'set-only','users':[{'name':'NUMERIC_LITERAL','operation':'set','value':'00000'}]},
       {'name':'delete-only','users':[{'name':'EMPTY_LITERAL','operation':'delete','value':None}]}]
(root/'expected.json').write_text(json.dumps({'before':expected,'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fullL04Accepted':False};outputs=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   async def call(name,args):
    value=await client.call_tool(name,args);assert not value.is_error,value;return value.structured_content['data']
   lid=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId']
   for case in cases:
    pid=next(p['objectId'] for p in (await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'] if p['name']=='MCP_RESVAR')
    plan=await call('capture_plan_library_package_edit',{'libraryId':lid,'packageId':pid,'userProperties':case['users']});key={k:plan[k] for k in ('planId','planDigest')}
    assert plan['preview']['changes']=={}
    result=await call('capture_apply_library_package_edit',{**key,'idempotencyKey':case['name']});opened=await call('capture_open_edited_library',{**key,'kind':'package'});lid=opened['libraryId']
    pid=next(p['objectId'] for p in (await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'] if p['name']=='MCP_RESVAR')
    data=await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':pid})
    if case['name']=='set-only':expected['NUMERIC_LITERAL']={**expected['NUMERIC_LITERAL'],'value':'00000'}
    else:del expected['EMPTY_LITERAL']
    assert {p['name']:p for p in data['properties']['userProperties']}==expected
    path=root/'work'/result['outputWorkspaceRelativePath']/'library.olb';outputs.append((path,sha256(path)))
    report['cases'].append({'name':case['name'],'key':key,'result':result,'after':data,'passed':True})
  async with Client(params,mode='legacy',read_timeout_seconds=120) as fresh:
   for case in report['cases']:
    applied=await fresh.call_tool('capture_apply_library_package_edit',{**case['key'],'idempotencyKey':case['name']});assert not applied.is_error and not applied.structured_content['data']['mutationReplayed']
    recovered=await fresh.call_tool('capture_recover_library_package_edit',case['key']);assert not recovered.is_error
    opened=await fresh.call_tool('capture_open_edited_library',{**case['key'],'kind':'package'});assert not opened.is_error
  report.update(passed=True,setOnlyAccepted=True,deleteOnlyAccepted=True,freshServerVerifyOnlyRecoveryAccepted=True,nativeOutputsUnchangedAcrossRecovery=all(sha256(p)==h for p,h in outputs))
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==source_hash;report['oracleUnchanged']=sha256(root/'expected.json')==oracle
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'] and report.get('nativeOutputsUnchangedAcrossRecovery',False)
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
