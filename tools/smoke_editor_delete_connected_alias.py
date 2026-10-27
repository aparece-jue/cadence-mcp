"""Delete a real pin-connected aliased wire; require explicit alias acknowledgement."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-delete-connected-alias-20261027';root.mkdir(exist_ok=False)
base=r/'.local/editor-wire-original-pins-mcp-20261027';old=json.loads((base/'report.json').read_text(encoding='utf-8'))['result'];source=base/'work'/old['outputWorkspaceRelativePath']/'design.dsn';before=sha256(source);assert before==old['artifact']['sha256']
expected=[{**pin,'connected':False,'net':None} for pin in old['expectedConnections']];(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';bindings=r/'.local/editor-wire-fresh-binding-20261027';env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
async def main():
 report={'passed':False,'sourceBefore':before}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content;return reply.structured_content['data']
   instance=(await call('capture_gui_instances',{}))['instances'][0];gui=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId'];ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0];wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items'];assert len(wires)==1
   args={'sessionId':sid,'wireId':wires[0]['objectId'],'operation':'delete','expectedConnections':expected,'guiSessionId':gui,'hostProject':str(project)}
   denied=await client.call_tool('capture_plan_wire_edit',args);assert denied.is_error and denied.structured_content['error']['code']=='alias_removal_required'
   plan=await call('capture_plan_wire_edit',{**args,'removeAttachedAliases':True});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   result=await call('capture_apply_wire_edit',{**key,'idempotencyKey':'delete-connected-wire-alias'});report['result']=result
   assert result['expectedDefinitionsVerified'] and result['outputProjectCloseVerified'] and result['hostContextPreserved']
   opened=await call('capture_open_edit_result',{**key,'kind':'wire_edit'});oid=opened['sessionId'];page=(await call('capture_query',{'sessionId':oid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   for kind in ('wire','alias'):
    actual=await call('capture_query_connections',{'sessionId':oid,'entity':kind,'pageId':page['objectId']});assert actual['total']==0
   compared=await call('capture_compare_connections',{'sessionId':oid,'expectedRevision':opened['revision'],'expectations':expected,'expectationSource':'two-resistor-explicit-open-after-wire-delete@1'});report['comparison']=compared;assert compared['comparisonStatus']=='pass'
   report.update(passed=True,explicitAliasAcknowledgementRequired=True,wireAndAliasRemoved=True,fourOriginalPinsExplicitlyUnbound=True,outputClosed=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('plan','result','comparison')}),flush=True)
asyncio.run(main())
