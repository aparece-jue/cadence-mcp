"""Native editor-backed public MCP wire add, verified outputs and no replay."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-wire-add-mcp-v2-20261027';root.mkdir(exist_ok=False)
source=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.dsn';project=source.with_suffix('.opj');before=sha256(source);project_before=sha256(project)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');bindings=r/'.local/editor-wire-fresh-binding-20261027'
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
def files():return {p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
async def main():
 report={'passed':False,'sourceBefore':before,'hostProjectBefore':project_before,'checks':{}};key=None
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   ts=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in ts};report['toolCount']=len(ts)
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content
    Draft202012Validator(schemas[name]).validate(reply.structured_content);return reply.structured_content['data']
   instances=await call('capture_gui_instances',{});gui=(await call('capture_gui_attach',{'instanceId':instances['instances'][0]['instanceId']}))['sessionId']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items']
   args={'sessionId':sid,'pageId':page['objectId'],'start':[100,600],'end':[300,600],'netName':'EDITOR_MCP','expectedConnections':[],'guiSessionId':gui,'hostProject':str(project)}
   rejected=await client.call_tool('capture_plan_wire_add',{k:v for k,v in args.items() if k!='hostProject'});assert rejected.is_error and rejected.structured_content['error']['code']=='invalid_editor_host'
   pending=await call('capture_plan_wire_add',args);pending_key={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_wire_add',pending_key)
   rejected=await client.call_tool('capture_apply_wire_add',{**pending_key,'idempotencyKey':'cancelled'});assert rejected.is_error
   plan=await call('capture_plan_wire_add',args);key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   result=await call('capture_apply_wire_add',{**key,'idempotencyKey':'editor-add'});report['result']=result
   assert result['hostContextPreserved'] and result['guiSessionReattachRequired'] and result['executionBackend']=='capture_editor'
   rejected=await client.call_tool('capture_gui_query',{'sessionId':gui,'entity':'status'});assert rejected.is_error
   instances=await call('capture_gui_instances',{});newgui=await call('capture_gui_attach',{'instanceId':instances['instances'][0]['instanceId']});await call('capture_gui_query',{'sessionId':newgui['sessionId'],'entity':'status'})
   opened=await call('capture_open_edit_result',{**key,'kind':'wire_add'});oid=opened['sessionId']
   outpage=(await call('capture_query',{'sessionId':oid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   observed=(await call('capture_query_connections',{'sessionId':oid,'entity':'wire','pageId':outpage['objectId']}))['items']
   aliases=(await call('capture_query_connections',{'sessionId':oid,'entity':'alias','pageId':outpage['objectId']}))['items']
   stable=lambda rows:sorted((tuple(map(tuple,w['attributes']['points'])),w['attributes']['net']) for w in rows)
   expected=wires+[{'attributes':{'points':[[100,600],[300,600]],'net':'EDITOR_MCP'}}]
   assert stable(observed)==stable(expected),'entire wire map changed'
   assert len(aliases)==1 and aliases[0]['attributes']['name']=='EDITOR_MCP' and aliases[0]['attributes']['location']==[100,600]
   report['checks'].update(nativePublicMcpAndReopen=True,entireWireMapPreserved=True,aliasSaved=True,oldGuiSessionInvalidated=True,explicitReattachAccepted=True,pendingCancelAndPairedHostArgs=True)
  frozen=files()
  async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
   for name,args in [('capture_apply_wire_add',{**key,'idempotencyKey':'editor-add'}),('capture_recover_wire_add',key)]:
    result=await fresh.call_tool(name,args);assert not result.is_error,result.structured_content;assert not result.structured_content['data']['mutationReplayed']
  assert files()==frozen,'verified repeat call changed task files';report['checks']['freshServerNoReplayAndAllFilesUnchanged']=True;report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['hostProjectUnchanged']=sha256(project)==project_before;report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('plan','result')}),flush=True)
asyncio.run(main())
