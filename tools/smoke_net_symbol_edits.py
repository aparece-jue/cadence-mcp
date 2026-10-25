"""Real MCP global/offpage rename/delete and durable acceptance."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);a.source_root=a.source_root.resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source_root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'phase':'start','cases':[],'sourcesBefore':{k:sha256(a.source_root/k/'design.dsn') for k in ('global','offpage')}};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==137;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   for kind in ('global','offpage'):
    ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source_root/kind/'design.dsn')});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];objs=(await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1000}))['items']+(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'];symbol=next(o for o in objs if o['kind']==kind and o['attributes']['name']==('MCP_SUPPLY' if kind=='global' else 'MCP_LINK'));wire=next(o for o in objs if o['kind']=='wire' and o['attributes']['points']==[[240,310],[290,310]]);base={'sessionId':sid,'symbolId':symbol['objectId'],'wireId':wire['objectId']}
    for bad in ({**base,'operation':'set_name'},{**base,'operation':'set_pose'},{**base,'operation':'set_name','name':'DATA[7..0]'},{**base,'operation':'delete','name':'X'},{**base,'operation':'set_name','name':'X','eval':'unsafe'},{**base,'operation':'set_name','name':'MCP_MIDDLE'}):assert (await client.call_tool('capture_plan_net_symbol_edit',bad)).is_error
    for operation in ('set_name','delete'):
     mode=kind+'-'+operation;report['phase']=mode;plan=await call('capture_plan_net_symbol_edit',{**base,'operation':operation,**({'name':'MCP_RENAMED'} if operation=='set_name' else {})});key={k:plan[k] for k in ('planId','planDigest')};keys.append((mode,key));run=await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':mode});assert run['nativePagePartitionsVerified'] and run['designPassed'] is None and not run['occurrenceConnectivityVerified'];opened=await call('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});obs=(await call('capture_query_connections',{'sessionId':opened['sessionId'],'entity':kind,'limit':1000}))['items'];assert any(o['attributes']['name']=='MCP_RENAMED' for o in obs) if operation=='set_name' else not any(o['attributes']['name']==symbol['attributes']['name'] for o in obs);report['cases'].append({'mode':mode,'plan':plan,'result':run})
    wrong=await call('capture_plan_net_symbol_edit',{**base,'operation':'set_name','name':'MCP_BAD','expectedWireNet':'WRONG'});wk={k:wrong[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_net_symbol_edit',{**wk,'idempotencyKey':kind+'-wrong'});assert v.is_error;assert (await client.call_tool('capture_open_edit_result',{**wk,'kind':'net_symbol_edit'})).is_error;v=await client.call_tool('capture_apply_net_symbol_edit',{**wk,'idempotencyKey':kind+'-wrong'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed'
    pending=await call('capture_plan_net_symbol_edit',{**base,'operation':'delete'});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_net_symbol_edit',pk);assert (await client.call_tool('capture_apply_net_symbol_edit',{**pk,'idempotencyKey':kind+'-cancel'})).is_error
   report['jobs']=await call('capture_net_symbol_edit_jobs',{'offset':0,'limit':1})
  report['phase']='fresh_server'
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   for mode,key in keys:
    v=await client.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':mode});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_net_symbol_edit',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_edit'})).is_error
   mode,key=keys[-1];path=root/'work/isolated-jobs/capture_net_symbol_edit'/('plan-'+key['planId'])/'design.dsn'
   with path.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});assert v.is_error and v.structured_content['error']['code']=='target_changed';report['freshNoReplayAndTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourcesAfter']={k:sha256(a.source_root/k/'design.dsn') for k in ('global','offpage')};report['passed'] &= report['sourcesBefore']==report['sourcesAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'phase':report['phase'],'cases':len(report['cases']),'error':report.get('error')}))
 return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)


