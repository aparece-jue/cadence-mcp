import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'checks':{}}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as c:
   r=await c.call_tool('capture_library_open',{'sourceLibrary':str(source)});assert not r.is_error;lid=r.structured_content['data']['libraryId'];r=await c.call_tool('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000});pin=r.structured_content['data']['items'][0];args={'libraryId':lid,'pinId':pin['objectId']}
   r=await c.call_tool('capture_get_library_pin_style',args);assert not r.is_error and len(r.structured_content['data']['flags'])==11;report['checks']['native_read_before_change']=True;directory=root/'work'/lid;requests=set(directory.glob('pin-style*.json'));target=directory/'library.olb';target.write_bytes(target.read_bytes()+b'owned copied-library stale test');r=await c.call_tool('capture_get_library_pin_style',args);assert r.is_error and r.structured_content['error']['code']=='target_changed' and set(directory.glob('pin-style*.json'))==requests;report['checks']['changed_copy_refused_before_worker_output']=True
   r=await c.call_tool('capture_library_close',{'libraryId':lid});assert not r.is_error;r=await c.call_tool('capture_get_library_pin_style',args);assert r.is_error and r.structured_content['error']['code']=='session_lost';report['checks']['closed_session_refused']=True
  report['checks']['source_unchanged']=sha256(source)==before;report['passed']=all(report['checks'].values())
 except BaseException as e:report['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
