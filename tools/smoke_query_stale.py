"""Live-session copy changes and original snapshot immutability, through actual MCP."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/query-stale-final-20261025';root.mkdir(exist_ok=False);source=repo/'.local/query-closure-20261025/sources/duplicate.dsn';before=sha256(source)
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   assert len((await client.list_tools()).tools)==167
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   args={'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1};page=await call('capture_query',args);assert page['total']==4 and page['nextCursor']
   snap=await call('capture_snapshot',{'sessionId':sid});path=root/'work'/ws['workspaceId']/snap['artifact']['workspaceRelativePath'];original_snapshot=path.read_bytes()
   second=await call('capture_open',{'workspaceId':ws['workspaceId']});fresh=await call('capture_query',{**args,'sessionId':second['sessionId']});assert fresh['items']==page['items'] and fresh['revision']==page['revision']
   copied=root/'work'/ws['workspaceId']/'design.dsn'
   with copied.open('ab') as stream:stream.write(b'OWNED_ACTIVE_SESSION_STALE_FIXTURE')
   for tool,values in [('capture_query',args),('capture_query',{**args,'cursor':page['nextCursor']}),('capture_snapshot',{'sessionId':sid}),('capture_open',{'workspaceId':ws['workspaceId']})]:
    r=await client.call_tool(tool,values);assert r.is_error and r.structured_content['error']['code']=='target_changed',(tool,r.structured_content)
   await call('capture_close',{'sessionId':sid});await call('capture_close',{'sessionId':second['sessionId']})
   assert path.read_bytes()==original_snapshot and sha256(path)==snap['artifact']['sha256'] and sha256(source)==before
   report.update(passed=True,opened=opened,snapshot=snap,checks={'fresh_reader_same_objects':True,'active_query_and_cursor_stale_rejected':True,'snapshot_and_reopen_stale_rejected':True,'stale_sessions_close_successfully':True,'source_and_original_snapshot_unchanged':True})
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
