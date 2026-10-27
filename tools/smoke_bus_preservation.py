"""Public MCP adds ADDR beside an existing DATA bus; preserves all old entry semantics."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from cadence_mcp.capture_bus_create import wire_groups,entry_rows

r=Path(__file__).resolve().parents[1]
root=r/'.local/bus-preservation-mcp-20261027';root.mkdir(exist_ok=False)
old=json.loads((r/'.local/bus-create-mcp-20261027/report.json').read_text(encoding='utf-8'))
case=next(c for c in old['cases'] if c['mode']=='descending')
source=r/'.local/bus-create-mcp-20261027/work'/case['result']['outputWorkspaceRelativePath']/'design.dsn'
assert sha256(source)==case['result']['artifact']['sha256']
before=sha256(source);project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';host_before=sha256(project)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(r/'.local/editor-wire-fresh-binding-20261027'),'--timeout-seconds','30'],env=env)
expected=dict(prefix='ADDR',firstIndex=0,lastIndex=7,busStart=[200,200],busEnd=[200,700],branches=[dict(index=i,entryPoint=[200,220+50*i],endPoint=[220,240+50*i],wireEnd=[400,240+50*i],expectedBusAttached=True) for i in range(8)],expectedConnections=[])
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
async def main():
 report=dict(passed=False,sourceBefore=before,oracleSha256=oracle)
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    result=await client.call_tool(name,args)
    assert not result.is_error,result.structured_content or result.content
    return result.structured_content['data']
   async def rows(sid):return {kind:(await call('capture_query_bus',dict(sessionId=sid,entity=kind,limit=1000)))['items'] for kind in ('bus','scalar','entry')}
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)))
   sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId']
   page=(await call('capture_query',dict(sessionId=sid,entity='page',scope=dict(kind='design'))))['items'][0]
   original=await rows(sid)
   gui=(await call('capture_gui_attach',dict(instanceId=(await call('capture_gui_instances',{}))['instances'][0]['instanceId'])))['sessionId']
   plan=await call('capture_plan_bus_create',dict(sessionId=sid,guiSessionId=gui,hostProject=str(project),pageId=page['objectId'],**expected))
   key={k:plan[k] for k in ('planId','planDigest')};report['plan']=key
   report['result']=await call('capture_apply_bus_create',dict(**key,idempotencyKey='preserve-existing-data'))
   opened=await call('capture_open_edit_result',dict(**key,kind='bus_create'));actual=await rows(opened['sessionId'])
   # Normalize snapshot IDs while comparing independent public observations.
   def normalize(data,prefix):
    wires={w['wireId']:w for w in data['bus']+data['scalar']}
    meta=lambda w:[w['name'],w['width'],[m['name'] for m in w['members']],w['points']]
    ws=sorted([meta(w) for w in wires.values() if w['name'].startswith(prefix)],key=str)
    es=sorted([[e['entryPoint'],e['endPoint'],None if e['entryWireId'] is None else wires[e['entryWireId']]['name'],None if e['endWireId'] is None else wires[e['endWireId']]['name']] for e in data['entry'] if e['endWireId'] is not None and wires[e['endWireId']]['name'].startswith(prefix)],key=str)
    return ws,es
   assert normalize(original,'DATA')==normalize(actual,'DATA')
   assert len(actual['entry'])==16 and len(actual['scalar'])==16
   addr=[w for w in actual['bus'] if w['name']=='ADDR[0..7]']
   assert addr and all([m['name'] for m in w['members']]==['ADDR'+str(i) for i in range(8)] for w in addr)
   assert report['result']['localEntryRoutingComplete']
   report.update(existingNamedGeometryAndNativeEntryLinksPreserved=True,combinedEntryCount=16,combinedScalarCount=16)
  snapshot={p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,args in [('capture_apply_bus_create',dict(**key,idempotencyKey='preserve-existing-data')),('capture_recover_bus_create',key)]:
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content;assert result.structured_content['data']['mutationReplayed'] is False
  assert snapshot=={p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
  report.update(passed=True,freshServiceFilesUnchanged=True)
 except BaseException:report['error']=traceback.format_exc()
 report.update(sourceUnchanged=sha256(source)==before,hostProjectUnchanged=sha256(project)==host_before,oracleUnchanged=sha256(root/'expected.json')==oracle)
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
