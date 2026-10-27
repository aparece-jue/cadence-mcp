"""Existing typed MCP edits on the independently reopened editor-created fixture."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-wire-edits-mcp-20261027';root.mkdir(exist_ok=False)
source=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.dsn';before=sha256(source)
assert before=='8184f7f92848f536e9bc7a7969b5b597fe62515b1dfe5fef1bcb814b5e599397'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','45'],env=env)
def files():return {p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
async def main():
 report={'passed':False,'sourceBefore':before,'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   schemas={t.name:t.output_schema for t in (await client.list_tools()).tools}
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content
    Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
   sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   for operation in ('set_endpoints','delete'):
    page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
    rows=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items']
    target=[[100,100],[300,100]] if operation=='set_endpoints' else [[100,120],[300,120]]
    wire=next(w for w in rows if w['attributes']['points']==target)
    args={'sessionId':sid,'wireId':wire['objectId'],'operation':operation,'expectedConnections':[]}
    if operation=='set_endpoints':args.update(start=[100,120],end=[300,120],aliasLocations=[],expectedWireNet='N00001')
    plan=await call('capture_plan_wire_edit',args);key={k:plan[k] for k in ('planId','planDigest')};keys.append((key,operation))
    result=await call('capture_apply_wire_edit',{**key,'idempotencyKey':operation})
    opened=await call('capture_open_edit_result',{**key,'kind':'wire_edit'});sid=opened['sessionId']
    page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
    after=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items']
    stable=lambda items:sorted((tuple(map(tuple,w['attributes']['points'])),w['attributes']['net']) for w in items)
    expected=[w for w in rows if w['objectId']!=wire['objectId']]
    if operation=='set_endpoints':expected=expected+[{'attributes':{'points':[[100,120],[300,120]],'net':'N00001'}}]
    assert stable(after)==stable(expected),'independent entire wire geometry/net map differs'
    report['cases'].append({'operation':operation,'plan':key,'result':result,'allWireGeometryAndNetIdentityVerified':True})
  frozen=files()
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for key,operation in keys:
    result=await client.call_tool('capture_apply_wire_edit',{**key,'idempotencyKey':operation});assert not result.is_error and not result.structured_content['data']['mutationReplayed']
    result=await client.call_tool('capture_recover_wire_edit',key);assert not result.is_error,result.structured_content
  assert files()==frozen,'fresh-service replay changed task files'
  report.update(passed=True,freshServerNoReplay=True,allTaskFilesUnchanged=True)
 except BaseException as error:report['error']=str(error)
 report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)
asyncio.run(main())
