"""Recover an already completed NET/ALS task whose MCP response validation failed."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for key in ('failed-root','binding','source-root','install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();old=a.failed_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
row=json.loads((old/'report.json').read_text());key={k:row['plan'][k] for k in ('planId','planDigest')}
job=old/'work/isolated-jobs/capture_pspice_netlist'/('plan-'+key['planId'])
before={str(p.relative_to(job)):sha256(p) for p in job.rglob('*') if p.is_file()}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(old/'work'),'--read-root',str(a.source_root.resolve(strict=True)),'--gui-bridge-config',str(a.binding.resolve(strict=True))],env=env)
async def main():
 async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
  reply=await client.call_tool('capture_recover_pspice_netlist',key)
  assert not reply.is_error,reply.structured_content
  result=reply.structured_content['data'];assert result['nativeCompletionVerified'] and result['mutationReplayed'] is False
 assert {str(p.relative_to(job)):sha256(p) for p in job.rglob('*') if p.is_file()}==before
 report={'passed':True,'mutationReplayed':False,'allPriorTaskFilesUnchanged':True,'result':result}
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ('passed','mutationReplayed','allPriorTaskFilesUnchanged')}))
asyncio.run(main())
