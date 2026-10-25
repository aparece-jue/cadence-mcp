"""Actual MCP immutable net-symbol source query and cursor acceptance."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.install_root/'tools/capture/library/capsym.olb';source=source.resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceBefore':sha256(source)}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==127;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   lib=await call('capture_library_open',{'sourceLibrary':str(source)});lid=lib['libraryId'];all_rows=[];cursor=None;first=None
   while True:
    page=await call('capture_query_net_symbols',{'libraryId':lid,'limit':1,'cursor':cursor});all_rows+=page['items'];cursor=page['nextCursor']
    if first is None:first=page
    if cursor is None:break
   assert len(all_rows)==21 and len({r['symbolId'] for r in all_rows})==21
   assert {'VCC','GND','0','OFFPAGELEFT-L','PORTLEFT-L'}<=set(r['name'] for r in all_rows)
   for kind,count in [('global',11),('port',8),('offpage',2)]:
    rows=await call('capture_query_net_symbols',{'libraryId':lid,'kind':kind,'limit':1000});assert rows['total']==count and all(r['kind']==kind for r in rows['items'])
   for bad in ({'libraryId':lid,'limit':2,'cursor':first['nextCursor']},{'libraryId':lid,'kind':'port','limit':1,'cursor':first['nextCursor']},{'libraryId':lid,'limit':True},{'libraryId':lid,'kind':'global','eval':'unsafe'}):assert (await client.call_tool('capture_query_net_symbols',bad)).is_error
   second=await call('capture_library_open',{'sourceLibrary':str(source)});assert (await client.call_tool('capture_query_net_symbols',{'libraryId':second['libraryId'],'limit':1,'cursor':first['nextCursor']})).is_error
   assert (await call('capture_query_net_symbols',{'libraryId':second['libraryId'],'limit':1000}))['items']==all_rows
   await call('capture_library_close',{'libraryId':lid});assert (await client.call_tool('capture_query_net_symbols',{'libraryId':lid})).is_error
   copy=root/'work'/second['libraryId']/'library.olb'
   with copy.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_query_net_symbols',{'libraryId':second['libraryId']});assert v.is_error and v.structured_content['error']['code']=='target_changed'
   report.update(passed=True,symbols=all_rows,checks={'paging_and_native_types':True,'cursor_kind_limit_session_binding':True,'strict_inputs':True,'close_and_tamper_rejection':True})
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceAfter']=sha256(source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
asyncio.run(main())
