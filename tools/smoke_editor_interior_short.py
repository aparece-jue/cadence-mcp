"""Original four-pin short oracle over the same frozen input; native editor add."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-interior-short-20261027';root.mkdir(exist_ok=False)
old=r/'.local/short-via-edit-20261023';ledger=old/'work/isolated-jobs/capture_wire_edit/plan-4818a5bed1254bdb87f65247d7d10933/plan.json'
p=json.loads(ledger.read_text(encoding='utf-8'))['plan']['payload'];source=Path(p['sourceDesign']);before=sha256(source);assert before==p['sourceFingerprint']
oracle=old/'expected.json';oracle_hash=sha256(oracle);normal=json.loads(oracle.read_text(encoding='utf-8'))['intended_design'];short=json.loads(oracle.read_text(encoding='utf-8'))['intentionally_created'];assert short==p['expectedConnections']
expected_paths=[[[290,310],[330,310]],[[330,310],[490,310]],[[490,310],[530,310]]]
(root/'geometry-expected.json').write_text(json.dumps({'paths':expected_paths,'newAlias':'SHORT_EXTENSION','location':[290,310],'canonicalNet':'MCP_MIDDLE'},indent=2),encoding='utf-8')
host_project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';bindings=r/'.local/editor-wire-fresh-binding-20261027'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(host_project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
async def main():
 report={'passed':False,'phase':'open','sourceBefore':before,'originalOracleSha256':oracle_hash}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content or result.content;return result.structured_content['data']
   instance=(await call('capture_gui_instances',{}))['instances'][0];gui=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   page=next(x for x in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if x['name']=='MCP_PLACE')
   plan=await call('capture_plan_wire_add',{'sessionId':sid,'pageId':page['objectId'],'start':p['start'],'end':p['end'],'netName':'SHORT_EXTENSION','aliasLocation':[290,310],'expectedWireNet':'MCP_MIDDLE','expectedConnections':short,'expectedWirePaths':expected_paths,'guiSessionId':gui,'hostProject':str(host_project)})
   key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan;report['phase']='native_short'
   report['result']=await call('capture_apply_wire_add',{**key,'idempotencyKey':'original-four-pin-short'})
   report['phase']='compare_original_normal_oracle';opened=await call('capture_open_edit_result',{**key,'kind':'wire_add'})
   compare=await call('capture_compare_connections',{'sessionId':opened['sessionId'],'expectedRevision':opened['revision'],'expectations':normal,'expectationSource':'original-series-resistor-four-pin-spec@1'})
   report['comparison']=compare;assert compare['comparisonStatus']=='fail' and compare['countsByStatus'].get('fail')==2 and compare['designPassed'] is None
   report['passed']=True;report['phase']='completed'
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['originalOracleUnchanged']=sha256(oracle)==oracle_hash;report['passed']=report['passed'] and report['sourceUnchanged'] and report['originalOracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('plan','result','comparison')}),flush=True)
asyncio.run(main())
