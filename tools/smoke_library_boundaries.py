"""Actual L01 read-root, junction and argument bounds without changing source OLBs."""
import asyncio,json,os,sys,shutil,_winapi
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/library-boundaries-20261025';root.mkdir(exist_ok=False);allowed=root/'allowed';outside=root/'outside';allowed.mkdir();outside.mkdir()
source=repo/'.local/library-part-variants-20261024/single/library.olb';before=sha256(source)
for path in (allowed/'inside.olb',allowed/'wrong.dsn',outside/'outside.olb'):shutil.copyfile(source,path)
_winapi.CreateJunction(str(outside),str(allowed/'escape'))
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(allowed),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[]}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for label,path,code in [('outside',outside/'outside.olb','path_denied'),('junction',allowed/'escape/outside.olb','path_denied'),('extension',allowed/'wrong.dsn','unsupported_input')]:
    result=await client.call_tool('capture_library_open',{'sourceLibrary':str(path)});assert result.is_error and result.structured_content['error']['code']==code,(label,result.structured_content);report['cases'].append({'case':label,'error':code})
   opened=await client.call_tool('capture_library_open',{'sourceLibrary':str(allowed/'inside.olb')});assert not opened.is_error;lid=opened.structured_content['data']['libraryId']
   for label,args in [('unknown-session',{'libraryId':'lib-unknown','entity':'pin'}),('limit-zero',{'libraryId':lid,'entity':'pin','limit':0}),('limit-large',{'libraryId':lid,'entity':'pin','limit':1001}),('entity',{'libraryId':lid,'entity':'unsupported'})]:
    result=await client.call_tool('capture_library_query',args);assert result.is_error,(label,result.structured_content);report['cases'].append({'case':label,'rejected':True})
   closed=await client.call_tool('capture_library_close',{'libraryId':lid});assert not closed.is_error
  assert sha256(source)==before and sha256(allowed/'inside.olb')==before and sha256(outside/'outside.olb')==before;report['passed']=len(report['cases'])==7;report['sourceCopiesUnchanged']=True
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
