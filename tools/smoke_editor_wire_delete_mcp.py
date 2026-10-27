"""Original unrelated-net-loss source: old backend must refuse, editor must preserve."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-delete-original-mcp-20261027';root.mkdir(exist_ok=False)
old=r/'.local/editor-wire-edits-mcp-20261027/work/isolated-jobs/capture_wire_edit/plan-340bbb7e4f954133a1e0da480f704313/plan.json';p=json.loads(old.read_text(encoding='utf-8'))['plan']['payload'];source=Path(p['sourceDesign']);before=sha256(source);assert before==p['sourceFingerprint']=='38ada8311e4520129a83684d7aaf0af7621a06243fa1f90f49c18fa8b5c679b2'
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';project_before=sha256(project);bindings=r/'.local/editor-wire-fresh-binding-20261027';env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
def files():return {f.relative_to(root/'work').as_posix():sha256(f) for f in (root/'work').rglob('*') if f.is_file()}
async def main():
 report={'passed':False,'sourceBefore':before,'checks':{}};key=None
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content;return reply.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items'];wire=next(w for w in wires if w['attributes']['points']==[[100,120],[300,120]])
   args={'sessionId':sid,'wireId':wire['objectId'],'operation':'delete','expectedConnections':[]}
   negative=await call('capture_plan_wire_edit',args);bad={k:negative[k] for k in ('planId','planDigest')}
   reply=await client.call_tool('capture_apply_wire_edit',{**bad,'idempotencyKey':'old-dbo-loss-must-refuse'});assert reply.is_error and reply.structured_content['error']['code']=='unrelated_wire_net_changed',reply.structured_content or reply.content
   assert (await client.call_tool('capture_open_edit_result',{**bad,'kind':'wire_edit'})).is_error
   assert (await client.call_tool('capture_apply_wire_edit',{**bad,'idempotencyKey':'old-dbo-loss-must-refuse'})).is_error
   report['negativePlan']=bad;report['checks']['originalStandaloneLossNowRefusedBeforeVerifiedOutput']=True
   instance=(await call('capture_gui_instances',{}))['instances'][0];gui=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId']
   plan=await call('capture_plan_wire_edit',{**args,'guiSessionId':gui,'hostProject':str(project)});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   report['result']=await call('capture_apply_wire_edit',{**key,'idempotencyKey':'native-editor-delete'})
   assert report['result']['unrelatedWireNetIdentityPreserved'] and report['result']['outputProjectCloseVerified']
   opened=await call('capture_open_edit_result',{**key,'kind':'wire_edit'});oid=opened['sessionId'];outpage=(await call('capture_query',{'sessionId':oid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   observed=(await call('capture_query_connections',{'sessionId':oid,'entity':'wire','pageId':outpage['objectId']}))['items']
   stable=lambda rows:sorted((tuple(map(tuple,w['attributes']['points'])),w['attributes']['net']) for w in rows)
   assert stable(observed)==stable([w for w in wires if w['objectId']!=wire['objectId']]),'native editor altered other geometry or nets'
   report['checks'].update(originalSameByteSource=True,editorDeleteAndIndependentReopen=True,entireRemainingWireNetMapPreserved=True,outputProjectClosureVerified=True)
  frozen=files()
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,args in [('capture_apply_wire_edit',{**key,'idempotencyKey':'native-editor-delete'}),('capture_recover_wire_edit',key)]:
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content;assert not reply.structured_content['data']['mutationReplayed']
  assert files()==frozen;report['checks']['freshServiceNoReplayAndAllTaskFilesUnchanged']=True;report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['hostProjectUnchanged']=sha256(project)==project_before;report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('plan','result')}),flush=True)
asyncio.run(main())
