"""Actual stdio hierarchy-reuse lifecycle acceptance on owned outputs."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','oracle'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--new-reference',default='halfadd_C');p.add_argument('--location',nargs=2,type=int,default=[2000,2000])
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
oracle=json.loads(a.oracle.read_text())['geometry'];pins=[{k:p[k] for k in ('name','number','hotSpot')} for p in oracle['pins']]
for pin in pins:pin['hotSpot']=[v+new-old for v,new,old in zip(pin['hotSpot'],a.location,oracle['location'])]
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'phase':'start','sourceBefore':sha256(a.source)}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==116;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    x=await client.call_tool(name,args);assert not x.is_error,x.content;Draft202012Validator(schemas[name]).validate(x.structured_content);return x.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   # Read the native definition ID from the immutable session rather than guessing it.
   rows=await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000});part=next(p for p in rows['items'] if p['reference']=='halfadd_A');placed=next(p for p in rows['items'] if p['reference']=='U1')
   args={'sessionId':sid,'partId':part['objectId'],'newReference':a.new_reference,'location':a.location,'expectedPins':pins}
   for bad in ({**args,'newReference':'halfadd_B'},{**args,'newReference':'bad\nref'},{**args,'partId':placed['objectId']},{**args,'expectedPins':pins[:-1]},{**args,'eval':'unsafe'}):
    assert (await client.call_tool('capture_plan_hierarchy_clone',bad)).is_error
   report['phase']='plan';plan=await call('capture_plan_hierarchy_clone',args);report['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')}
   report['phase']='apply';run=await call('capture_apply_hierarchy_clone',{**key,'idempotencyKey':'clone'});report['result']=run
   assert run['partitionChecks']['privateNetsIsolated'] and run['originalOccurrencePropertiesVerified'] and run['designPassed'] is None
   opened=await call('capture_open_edit_result',{**key,'kind':'hierarchy_clone'});tree=await call('capture_get_hierarchy',{'sessionId':opened['sessionId'],'limit':1000});assert tree['total']==23
   report['phase']='cancel';pending=await call('capture_plan_hierarchy_clone',args);pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_hierarchy_clone',pk)
   assert (await client.call_tool('capture_apply_hierarchy_clone',{**pk,'idempotencyKey':'cancel'})).is_error
   report['jobs']=await call('capture_hierarchy_clone_jobs',{'offset':0,'limit':1})
  report['phase']='fresh_server'
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def fresh(name,args):
    x=await client.call_tool(name,args);assert not x.is_error,x.content;return x.structured_content['data']
   cached=await fresh('capture_apply_hierarchy_clone',{**key,'idempotencyKey':'clone'});assert not cached['mutationReplayed']
   await fresh('capture_recover_hierarchy_clone',key);await fresh('capture_open_edit_result',{**key,'kind':'hierarchy_clone'})
   d=root/'work/isolated-jobs/capture_hierarchy_clone'/('plan-'+key['planId']);target=d/'design.dsn'
   with target.open('ab') as f:f.write(b'controlled-tamper-negative')
   x=await client.call_tool('capture_open_edit_result',{**key,'kind':'hierarchy_clone'});assert x.is_error and x.structured_content['error']['code']=='target_changed'
   report['freshNoReplayAndTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error')}))
asyncio.run(main())
