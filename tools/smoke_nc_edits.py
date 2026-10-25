"""Actual stdio NC add/remove chain and durable lifecycle verification."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--reference',default='R101');p.add_argument('--expected-hotspot',type=int,nargs=2,default=[290,310]);p.add_argument('--both-pins-unbound',action='store_true')
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'phase':'start','sourceBefore':sha256(a.source),'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==121;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   rows=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'reference':a.reference,'limit':1000}))['items'];pin=next(p for p in rows if p['number']=='1');connected=next(p for p in rows if p['number']=='2')
   args={'sessionId':sid,'pinId':pin['objectId'],'enabled':True}
   bad_inputs=[{**args,'enabled':1},{**args,'enabled':False},{**args,'pinId':'missing'},{**args,'eval':'unsafe'}]
   if not a.both_pins_unbound:bad_inputs.append({**args,'pinId':connected['objectId']})
   for bad in bad_inputs:assert (await client.call_tool('capture_plan_nc_edit',bad)).is_error
   for name,enabled in [('add',True),('remove',False)]:
    report['phase']=name;plan=await call('capture_plan_nc_edit',{'sessionId':sid,'pinId':pin['objectId'],'enabled':enabled});key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key))
    result=await call('capture_apply_nc_edit',{**key,'idempotencyKey':name});assert result['scalarPinNCVerified'] and result['expectedNC']==enabled and result['designPassed'] is None
    opened=await call('capture_open_edit_result',{**key,'kind':'nc'});sid=opened['sessionId'];nc=await call('capture_query_connections',{'sessionId':sid,'entity':'nc','limit':1000});assert nc['total']==int(enabled)
    if enabled:assert nc['items'][0]['attributes']['hotSpot']==a.expected_hotspot and nc['items'][0]['attributes']['reference']==a.reference
    rows=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'reference':a.reference,'limit':1000}))['items'];pin=next(p for p in rows if p['number']=='1')
    report['cases'].append({'operation':name,'plan':plan,'result':result,'nc':nc})
   pending=await call('capture_plan_nc_edit',{'sessionId':sid,'pinId':pin['objectId'],'enabled':True});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_nc_edit',pk);assert (await client.call_tool('capture_apply_nc_edit',{**pk,'idempotencyKey':'cancel'})).is_error
   report['jobs']=await call('capture_nc_edit_jobs',{'offset':0,'limit':1})
  report['phase']='fresh_server'
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_nc_edit',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed']
    assert not (await client.call_tool('capture_recover_nc_edit',key)).is_error
    assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'nc'})).is_error
   name,key=keys[-1];target=root/'work/isolated-jobs/capture_nc'/('plan-'+key['planId'])/'design.dsn'
   with target.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'nc'});assert v.is_error and v.structured_content['error']['code']=='target_changed'
   report['freshNoReplayAndTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error')}))
asyncio.run(main())
