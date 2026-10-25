import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceBefore':before,'scope':'case-insensitive preflight refusal; no new native write acceptance'}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   report['tools']=len((await client.list_tools()).tools);assert report['tools']==137
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];symbols=(await call('capture_query_connections',{'sessionId':sid,'entity':'global','limit':1000}))['items'];wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'];symbol=next(o for o in symbols if o['attributes']['name']=='MCP_SUPPLY');wire=next(o for o in wires if o['attributes']['points']==[[240,310],[290,310]])
   codes=[]
   for name in ('mcp_middle','McP_MiDdLe','MCP_MIDDLE'):
    v=await client.call_tool('capture_plan_net_symbol_edit',{'sessionId':sid,'symbolId':symbol['objectId'],'wireId':wire['objectId'],'operation':'set_name','name':name});assert v.is_error and v.structured_content['error']['code']=='net_symbol_merge_unsupported';codes.append({'name':name,'errorCode':v.structured_content['error']['code']})
   report['rejected']=codes;report['privateCopyUnchanged']=sha256(root/'work'/ws['workspaceId']/'design.dsn')==before;report['durablePlanFiles']=len(list((root/'work/isolated-jobs/capture_net_symbol_edit').glob('*/plan.json')));assert report['durablePlanFiles']==0 and report['privateCopyUnchanged'];report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceAfter']=sha256(source);report['passed'] &= report['sourceAfter']==before;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='traceback'}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
