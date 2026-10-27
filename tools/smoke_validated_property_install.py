import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
import cadence_mcp
assert cadence_mcp.__version__=='0.1.0' and 'site-packages' in cadence_mcp.__file__
r=Path(__file__).resolve().parents[1];root=r/'.local/v010-test/property-library';root.mkdir(exist_ok=False)
prior=json.loads((r/'.local/bus-eight-pins-mcp-20261027/report.json').read_text(encoding='utf-8'));case=prior['cases'][0];source=r/'.local/bus-eight-pins-mcp-20261027/work'/case['result']['outputWorkspaceRelativePath']/'design.dsn';before=sha256(source)
lp=json.loads((r/'.local/design-create-mcp-20261023/work/isolated-jobs/capture_placement/plan-d2513d885dda4930b5213f7b3c8f9c91/plan.json').read_text(encoding='utf-8'))['plan']['payload'];lib=Path(lp['sourceLibrary']);lib_before=sha256(lib)
env=os.environ.copy();env.pop('PYTHONPATH',None);params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.validated_server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(lib.parent),'--timeout-seconds','30'],env=env)
async def main():
 report=dict(passed=False,sourceBefore=before)
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content;return reply.structured_content['data']
   library=await call('capture_library_open',dict(sourceLibrary=str(lib)))
   for entity in ('package','device','cell','part','pin'):
    rows=await call('capture_library_query',dict(libraryId=library['libraryId'],entity=entity,packageName='MCP_RES',limit=1000));assert rows['items']
   await call('capture_library_close',dict(libraryId=library['libraryId']));report['libraryFiveEntitiesPassed']=True
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId'];parts=(await call('capture_query',dict(sessionId=sid,entity='part',scope=dict(kind='design'))))['items'];part=next(p for p in parts if p['reference']=='R501')
   await call('capture_get_property_layers',dict(sessionId=sid,partId=part['objectId']))
   plan=await call('capture_plan_property',dict(sessionId=sid,partId=part['objectId'],propertyName='Value',value='2k'));key={k:plan[k] for k in ('planId','planDigest')};report['plan']=key;report['result']=await call('capture_apply_property',dict(**key,idempotencyKey='validated-property'))
   opened=await call('capture_open_edit_result',dict(**key,kind='property'));outparts=(await call('capture_query',dict(sessionId=opened['sessionId'],entity='part',scope=dict(kind='design'))))['items'];outpart=next(p for p in outparts if p['reference']=='R501');props=await call('capture_get_part_properties',dict(sessionId=opened['sessionId'],partId=outpart['objectId']));assert any(p['name']=='Value' and p['value']=='2k' for p in props['items'])
   rows=(await call('capture_query_bus',dict(sessionId=opened['sessionId'],entity='pin_member',limit=100)))['items'];assert len(rows)==8 and all(p['hasMember'] for p in rows);report['eightPinMembershipPreserved']=True
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,args in [('capture_apply_property',dict(**key,idempotencyKey='validated-property')),('capture_recover_property',key)]:
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content;assert not result.structured_content['data']['mutationReplayed']
  report.update(passed=True,freshServerNoReplay=True)
 except BaseException:report['error']=traceback.format_exc()
 report.update(sourceUnchanged=sha256(source)==before,libraryUnchanged=sha256(lib)==lib_before);report['passed']=report['passed'] and report['sourceUnchanged'] and report['libraryUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
