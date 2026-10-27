"""Missing/wrong occurrence refuses before OPage or mutation, restores clean host."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from cadence_mcp.native_host_fence import read_fence
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-repeated-refusals-20261027';root.mkdir(exist_ok=False)
p=json.loads((r/'.local/short-via-edit-20261023/work/isolated-jobs/capture_wire_edit/plan-4818a5bed1254bdb87f65247d7d10933/plan.json').read_text(encoding='utf-8'))['plan']['payload'];source=Path(p['sourceDesign']);before=sha256(source);project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';bindings=r/'.local/editor-wire-fresh-binding-20261027'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
async def main():
 report={'passed':False,'cases':[]}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    res=await client.call_tool(name,args);assert not res.is_error,res.structured_content or res.content;return res.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];page=next(x for x in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if x['name']=='MCP_PLACE')
   for occurrence,error in [(None,'explicit_editor_occurrence_required'),('missing_instance','invalid_editor_occurrence')]:
    instance=(await call('capture_gui_instances',{}))['instances'][0];gui=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId']
    args={'sessionId':sid,'pageId':page['objectId'],'start':p['start'],'end':p['end'],'netName':'SHORT_EXTENSION','aliasLocation':[290,310],'expectedWireNet':'MCP_MIDDLE','expectedConnections':p['expectedConnections'],'expectedWirePaths':[[[290,310],[330,310]],[[330,310],[490,310]],[[490,310],[530,310]]],'guiSessionId':gui,'hostProject':str(project)}
    if occurrence is not None:args['editorOccurrence']=occurrence
    plan=await call('capture_plan_wire_add',args);key={k:plan[k] for k in ('planId','planDigest')};reply=await client.call_tool('capture_apply_wire_add',{**key,'idempotencyKey':'refuse-before-editor'})
    assert reply.is_error and reply.structured_content['error']['code']=='native_write_failed',reply.structured_content or reply.content
    d=root/'work/isolated-jobs/capture_wire_add'/('plan-'+key['planId']);receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));row=json.loads((d/'plan.json').read_text(encoding='utf-8'))
    assert receipt['error']==error and receipt['phase']=='open_page' and receipt['saved'] is False and receipt['hostRestored'] is True,receipt
    assert sha256(d/'design.dsn')==before and not (d/'design.dsnlck').exists();assert read_fence(Path(row['plan']['payload']['editorHost']['bindingPath'])) is None
    assert (await client.call_tool('capture_open_edit_result',{**key,'kind':'wire_add'})).is_error
    repeat=await client.call_tool('capture_apply_wire_add',{**key,'idempotencyKey':'refuse-before-editor'});assert repeat.is_error and repeat.structured_content['error']['code']=='write_not_replayed'
    report['cases'].append({'occurrence':occurrence,'receipt':receipt,'sourceCopyUnchanged':True,'outputClosed':True,'hostRestored':True,'fenceReleasedOnKnownRefusal':True,'noReplay':True})
   report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
