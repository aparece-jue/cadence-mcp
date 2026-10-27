"""Real pin connection plus deliberately wrong caller pin expectation through public MCP."""
import asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];root=r/'.local/bus-pin-mcp-20261027';root.mkdir(exist_ok=False)
old=json.loads((r/'.local/editor-wire-original-pins-mcp-20261027/report.json').read_text(encoding='utf-8'))['result']
source=r/'.local/editor-wire-original-pins-mcp-20261027/work'/old['outputWorkspaceRelativePath']/'design.dsn';before=sha256(source)
assert before==old['artifact']['sha256']
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';host_before=sha256(project)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(r/'.local/editor-wire-fresh-binding-20261027'),'--timeout-seconds','30'],env=env)
expected=dict(prefix='PIN',firstIndex=1,lastIndex=0,busStart=[200,200],busEnd=[200,600],branches=[dict(index=0,entryPoint=[200,280],endPoint=[220,300],wireEnd=[280,300],expectedBusAttached=True),dict(index=1,entryPoint=[200,380],endPoint=[220,400],wireEnd=[400,400],expectedBusAttached=True)],expectedConnections=copy.deepcopy(old['expectedConnections']))
pin=next(p for p in expected['expectedConnections'] if p['reference']=='R501' and p['pinNumber']=='1');pin.update(connected=True,net='PIN0')
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
async def main():
 report=dict(passed=False,sourceBefore=before,oracleSha256=oracle,cases=[])
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content
    return reply.structured_content['data']
   async def attach():return (await call('capture_gui_attach',dict(instanceId=(await call('capture_gui_instances',{}))['instances'][0]['instanceId'])))['sessionId']
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId']
   page=(await call('capture_query',dict(sessionId=sid,entity='page',scope=dict(kind='design'))))['items'][0]
   for wrong in (False,True):
    item=dict(wrongExpectation=wrong,passed=False);report['cases'].append(item)
    args=copy.deepcopy(expected)
    if wrong:args['expectedConnections']=copy.deepcopy(old['expectedConnections'])
    plan=await call('capture_plan_bus_create',dict(sessionId=sid,guiSessionId=await attach(),hostProject=str(project),pageId=page['objectId'],**args))
    key={k:plan[k] for k in ('planId','planDigest')};item['plan']=key
    reply=await client.call_tool('capture_apply_bus_create',dict(**key,idempotencyKey='wrong' if wrong else 'correct'))
    if wrong:
     assert reply.is_error and reply.structured_content['error']['code']=='bus_pin_mismatch',reply.structured_content
     item['rejectedWith']=reply.structured_content['error']['code']
     d=root/'work/isolated-jobs/capture_bus_create'/('plan-'+key['planId'])
     receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));assert all(receipt[k] for k in ('saved','hostRestored','invocationReturned'))
     frozen={p.name:sha256(p) for p in d.iterdir() if p.is_file()}
     rejected=await client.call_tool('capture_open_edit_result',dict(**key,kind='bus_create'));assert rejected.is_error
     rejected=await client.call_tool('capture_apply_bus_create',dict(**key,idempotencyKey='wrong'));assert rejected.is_error and rejected.structured_content['error']['code']=='write_not_replayed'
     assert frozen=={p.name:sha256(p) for p in d.iterdir() if p.is_file()}
     item.update(realNativeSaveBeforeOracleRejection=True,unverifiedOutputRefused=True,replayRefusedAndFilesUnchanged=True)
    else:
     assert not reply.is_error,reply.structured_content;item['result']=reply.structured_content['data']
     opened=await call('capture_open_edit_result',dict(**key,kind='bus_create'))
     pins=(await call('capture_query',dict(sessionId=opened['sessionId'],entity='pin',scope=dict(kind='design'))))['items']
     actual=next(p for p in pins if p['reference']=='R501' and p['number']=='1')
     assert actual['connected'] and actual['net']=='PIN0';item['physicalPinObserved']=actual
    item['passed']=True;print(json.dumps(dict(wrongExpectation=wrong,passed=True)),flush=True)
  report['passed']=len(report['cases'])==2 and all(c['passed'] for c in report['cases'])
 except BaseException:report['error']=traceback.format_exc()
 report.update(sourceUnchanged=sha256(source)==before,hostProjectUnchanged=sha256(project)==host_before,oracleUnchanged=sha256(root/'expected.json')==oracle)
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)
asyncio.run(main())
