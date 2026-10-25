"""Actual stdio standalone alias name/anchor/delete and lifecycle acceptance."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'phase':'start','cases':[],'sourceBefore':sha256(a.source)};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==126;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];aliases=await call('capture_query_connections',{'sessionId':sid,'entity':'alias','limit':1000});alias=next(x for x in aliases['items'] if x['attributes']['name']=='MCP_MIDDLE');base={'sessionId':sid,'aliasId':alias['objectId']}
   for bad in ({**base,'operation':'set'},{**base,'operation':'set','location':[400,311]},{**base,'operation':'set','name':'DATA[7..0]'},{**base,'operation':'delete','name':'X'},{**base,'operation':'set','name':'X','eval':'unsafe'}):assert (await client.call_tool('capture_plan_alias_edit',bad)).is_error
   for mode,args in [('rename',{'operation':'set','name':'MCP_RENAMED'}),('move',{'operation':'set','location':[400,310]}),('delete',{'operation':'delete'})]:
    report['phase']=mode;plan=await call('capture_plan_alias_edit',{**base,**args});key={k:plan[k] for k in ('planId','planDigest')};keys.append((mode,key));run=await call('capture_apply_alias_edit',{**key,'idempotencyKey':mode});assert run['nativePagePartitionsVerified'] and run['designPassed'] is None
    out=await call('capture_open_edit_result',{**key,'kind':'alias'});osid=out['sessionId'];obs=(await call('capture_query_connections',{'sessionId':osid,'entity':'alias','limit':1000}))['items']
    if mode=='delete':assert not any(o['attributes']['name']=='MCP_MIDDLE' for o in obs)
    else:
     target=next(o for o in obs if o['attributes']['name']==('MCP_RENAMED' if mode=='rename' else 'MCP_MIDDLE'));assert target['attributes']['location']==([400,310] if mode=='move' else [330,310])
    pins=(await call('capture_query',{'sessionId':osid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];selected=[p for p in pins if p['reference'] in ('R101','R102')]
    for pin in selected:
     connected=(pin['reference'],pin['number']) in {('R101','2'),('R102','1')};assert pin['connected']==connected
     if connected:assert pin['net']==run['observedWireNet']
    report['cases'].append({'mode':mode,'plan':plan,'result':run,'pins':selected})
   wrong=await call('capture_plan_alias_edit',{**base,'operation':'set','name':'MCP_BAD','expectedWireNet':'WRONG'});wk={k:wrong[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_alias_edit',{**wk,'idempotencyKey':'wrong'});assert v.is_error and v.structured_content['error']['code']=='alias_owner_name_mismatch';assert (await client.call_tool('capture_open_edit_result',{**wk,'kind':'alias'})).is_error
   v=await client.call_tool('capture_apply_alias_edit',{**wk,'idempotencyKey':'wrong'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOwnerOracleRejected']=True
   pending=await call('capture_plan_alias_edit',{**base,'operation':'delete'});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_alias_edit',pk);assert (await client.call_tool('capture_apply_alias_edit',{**pk,'idempotencyKey':'cancel'})).is_error;report['jobs']=await call('capture_alias_edit_jobs',{'offset':0,'limit':1})
  report['phase']='fresh_server'
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for mode,key in keys:
    v=await client.call_tool('capture_apply_alias_edit',{**key,'idempotencyKey':mode});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_alias_edit',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'alias'})).is_error
   mode,key=keys[-1];path=root/'work/isolated-jobs/capture_alias_edit'/('plan-'+key['planId'])/'design.dsn'
   with path.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'alias'});assert v.is_error and v.structured_content['error']['code']=='target_changed';report['freshNoReplayAndTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'phase':report['phase'],'cases':len(report['cases']),'error':report.get('error')}))
asyncio.run(main())
