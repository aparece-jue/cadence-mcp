"""Public property deletion must restore known native cache default, not absence."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];source=repo/'.local/property-layers-probe-v4-20261025/sources/override.dsn';root=repo/'.local/property-fallback-public-20261025';root.mkdir(exist_ok=False);before=sha256(source)
expected={'fallback':'库默认值','local':''.join(['料号','[x]','$',';',chr(34),chr(92),chr(10),'尾'])};(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   sch=(await call('capture_query',{'sessionId':sid,'entity':'schematic','scope':{'kind':'design'}}))['items'];rootid=next(s['objectId'] for s in sch if s['name']=='ROOT')
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','reference':'R1','scope':{'kind':'design'}}))['items'];part=next(p for p in parts if p['schematicId']==rootid)
   args={'sessionId':sid,'partId':part['objectId'],'operation':'delete','propertyName':'MCP_DEFAULT'}
   plan=await call('capture_plan_user_property',{**args,'expectedEffectiveAfterDelete':expected['fallback']});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   report['result']=await call('capture_apply_user_property',{**key,'idempotencyKey':'default-fallback'})
   edited=await call('capture_open_edit_result',{**key,'kind':'user_property'});layer=await call('capture_get_property_layers',{'sessionId':edited['sessionId'],'partId':part['objectId']});effective={v['name']:v['value'] for v in layer['effective']};user={v['name']:v['value'] for v in layer['user']}
   assert effective['MCP_DEFAULT']==expected['fallback'] and 'MCP_DEFAULT' not in user and user['MCP_LOCAL']==expected['local'];report['layers']=layer
   bad=await call('capture_plan_user_property',{**args,'expectedEffectiveAfterDelete':None});badkey={k:bad[k] for k in ('planId','planDigest')};report['negativePlan']=bad
   r=await client.call_tool('capture_apply_user_property',{**badkey,'idempotencyKey':'wrong-absence'});assert r.is_error and r.structured_content['error']['code']=='effective_fallback_mismatch',r.structured_content
   r=await client.call_tool('capture_open_edit_result',{**badkey,'kind':'user_property'});assert r.is_error
   r=await client.call_tool('capture_apply_user_property',{**badkey,'idempotencyKey':'wrong-absence'});assert r.is_error and r.structured_content['error']['code']=='write_not_replayed'
   report['checks']['known_default_restored_and_wrong_absence_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   r=await fresh.call_tool('capture_apply_user_property',{**key,'idempotencyKey':'default-fallback'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
   r=await fresh.call_tool('capture_recover_user_property',key);assert not r.is_error
  report['checks']['fresh_lifecycle_no_replay']=True;report['checks']['source_and_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
