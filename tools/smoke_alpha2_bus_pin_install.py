"""Read all physical-member cases through actual public MCP; no writes to DSN."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
import cadence_mcp
assert cadence_mcp.__version__=='0.1.0a2' and 'site-packages' in cadence_mcp.__file__
r=Path(__file__).resolve().parents[1];root=r/'.local/alpha2-test/bus-pin-query';root.mkdir(exist_ok=False)
prior_root=r/'.local/bus-eight-pins-mcp-20261027';prior=json.loads((prior_root/'report.json').read_text(encoding='utf-8'));assert prior['passed']
expected=json.loads((prior_root/'expected.json').read_text(encoding='utf-8'));oracle=sha256(prior_root/'expected.json')
env=os.environ.copy();env.pop('PYTHONPATH',None)
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(prior_root),'--read-root',str(r/'.local/connection-inventory-matrix-v2-20261025'),'--timeout-seconds','30'],env=env)
async def main():
 report=dict(passed=False,cases=[],oracleSha256=oracle)
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content;Draft202012Validator(schemas[name]).validate(reply.structured_content);return reply.structured_content['data']
   for case in prior['cases']:
    mode=case['mode'];source=prior_root/'work'/case['result']['outputWorkspaceRelativePath']/'design.dsn';before=sha256(source)
    ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId']
    first=await call('capture_query_bus',dict(sessionId=sid,entity='pin_member',limit=1));rows=first['items'];cursor=first['nextCursor']
    assert first['total']==8 and first['scope']=='same_page_design_definition_native_net_membership'
    while cursor:
     page=await call('capture_query_bus',dict(sessionId=sid,entity='pin_member',limit=1,cursor=cursor));rows+=page['items'];cursor=page['nextCursor']
    assert len(rows)==8
    for m in expected['mapping']:
     row=next(row for row in rows if row['reference']==m['reference'] and row['pinNumber']==m['pinNumber']);connected=not(mode=='missing_member' and m['index']==7)
     assert row['hasMember']==connected and row['memberPointerEqualsPinNet']==connected
     assert row['position']==((m['index'] if mode=='ascending' else 7-m['index']) if connected else -1)
    for args in [dict(entity='pin_member',limit=2),dict(entity='bus',limit=1)]:
     rejected=await client.call_tool('capture_query_bus',dict(sessionId=sid,cursor=first['nextCursor'],**args));assert rejected.is_error and rejected.structured_content['error']['code']=='stale_cursor'
    await call('capture_close',dict(sessionId=sid));rejected=await client.call_tool('capture_query_bus',dict(sessionId=sid,entity='pin_member'));assert rejected.is_error
    assert sha256(source)==before;report['cases'].append(dict(mode=mode,passed=True,physicalPinCount=8,memberCount=sum(row['hasMember'] for row in rows)));print(json.dumps(report['cases'][-1]),flush=True)
   # Four placed-resistor source has no bus: empty and no mutation.
   source=prior_root/'work'/prior['placements'][-1]['result']['outputWorkspaceRelativePath']/'design.dsn'
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId'];empty=await call('capture_query_bus',dict(sessionId=sid,entity='pin_member'));assert empty['total']==0 and empty['complete'];report['noBusEmptyAccepted']=True
   design=root/'work'/ws['workspaceId']/'design.dsn'
   # Locate this exact immutable workspace using its returned path rather than inventing layout.
   design=next(p for p in (root/'work').rglob('design.dsn') if p.parent.name==ws['workspaceId']) if not design.exists() else design
   saved=design.read_bytes()
   try:
    design.write_bytes(saved+b'tamper');rejected=await client.call_tool('capture_query_bus',dict(sessionId=sid,entity='pin_member'));assert rejected.is_error and rejected.structured_content['error']['code']=='target_changed'
   finally:design.write_bytes(saved)
   report['cachedFingerprintRechecked']=True
   report['passed']=len(report['cases'])==4 and all(c['passed'] for c in report['cases'])
 except BaseException:report['error']=traceback.format_exc()
 report['oracleUnchanged']=sha256(prior_root/'expected.json')==oracle;report['passed']=report['passed'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
