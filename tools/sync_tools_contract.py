"""Refresh tool contract from the actual stdio server, not hand-written schemas."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--server-module',default='cadence_mcp.server');a=p.parse_args()
async def main():
 env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m',a.server_module,'--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(a.workspace_root.resolve()),'--read-root',str(a.workspace_root.resolve().parent)],env=env)
 async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
  ts=(await client.list_tools()).tools;assert len({t.name for t in ts})==len(ts);a.output.write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({'tools':len(ts),'output':str(a.output)}))
asyncio.run(main())


