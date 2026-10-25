"""Complete the failed harness lifecycle using its four immutable accepted jobs."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','previous-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);previous=a.previous_root.resolve(strict=True);old=previous/'report.json';oldsha=sha256(old);doc=json.loads(old.read_text());assert len(doc['cases'])==4 and not doc['passed'];a.source_root=a.source_root.resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(previous/'work'),'--read-root',str(a.source_root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'originalReportSha256':oldsha,'originalReportStillFailed':True,'cases':[]}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==137;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   for row in doc['cases']:
    mode=row['mode'];key={k:row['plan'][k] for k in ('planId','planDigest')};path=previous/'work/isolated-jobs/capture_net_symbol_edit'/('plan-'+key['planId'])/'design.dsn';before=sha256(path);value=await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':mode});assert not value['mutationReplayed'];await call('capture_recover_net_symbol_edit',key);await call('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});assert before==sha256(path)==value['artifact']['sha256'];report['cases'].append({'mode':mode,'key':key,'outputSha256':before,'mutationReplayed':False})
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source_root/'offpage/design.dsn')});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];symbols=(await call('capture_query_connections',{'sessionId':sid,'entity':'offpage','limit':1000}))['items'];wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'];symbol=next(o for o in symbols if o['attributes']['name']=='MCP_LINK');wire=next(o for o in wires if o['attributes']['points']==[[240,310],[290,310]]);base={'sessionId':sid,'symbolId':symbol['objectId'],'wireId':wire['objectId']}
   wrong=await call('capture_plan_net_symbol_edit',{**base,'operation':'set_name','name':'MCP_BAD','expectedWireNet':'WRONG'});key={k:wrong[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':'offpage-wrong-unique'});assert v.is_error and v.structured_content['error']['code']=='alias_owner_name_mismatch';assert (await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_edit'})).is_error;v=await client.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':'offpage-wrong-unique'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['offpageWrongOracleRejectedWithoutReplay']=True
   pending=await call('capture_plan_net_symbol_edit',{**base,'operation':'delete'});key={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_net_symbol_edit',key);assert (await client.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':'offpage-cancel-unique'})).is_error;report['offpagePendingCancel']=True;report['jobs']=await call('capture_net_symbol_edit_jobs',{'offset':0,'limit':1})
   row=doc['cases'][-1];key={k:row['plan'][k] for k in ('planId','planDigest')};path=previous/'work/isolated-jobs/capture_net_symbol_edit'/('plan-'+key['planId'])/'design.dsn'
   with path.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});assert v.is_error and v.structured_content['error']['code']=='target_changed';report['lastOffpageDeleteOutputIntentionallyTamperedAndRejected']=True
  report['passed']=sha256(old)==oldsha and all(sha256(a.source_root/k/'design.dsn')==doc['sourcesBefore'][k] for k in ('global','offpage'))
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cachedJobs':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
