"""Recover existing completed preserved-byte CLI output by verification only; never execute/apply."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];original=r/'.local/preserved-cli-mcp-v2-20261026';root=r/'.local/preserved-cli-recovery-20261026';root.mkdir(exist_ok=False);run=json.loads((original/'report.json').read_text(encoding='utf-8'));key={k:run['plan'][k] for k in ('planId','planDigest')};job=original/'work/isolated-jobs/pspice_cli_run'/('plan-'+key['planId']);hashes={n:sha256(job/n) for n in ('input.cir','input.out','input.dat','result.out','result.dat','cli-receipt.json')};env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(original/'work'),'--read-root',str(original),'--timeout-seconds','120'],env=env);report={'passed':False,'originalFailureRetained':True,'noNativeReplay':True}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args)
    if v.is_error:raise AssertionError((name,v.structured_content))
    return v.structured_content['data']
   report['recovery']=await call('pspice_recover_cli_run',key);assert report['recovery']['numericalAcceptanceVerified'];report['output']=await call('pspice_inspect_run_output',{**key,'backend':'cli'});assert not report['output']['hasErrorDiagnostics'];report['dat']=await call('pspice_open_run_dat',{**key,'backend':'cli'});assert report['dat']['jobAssociationVerified'];await call('pspice_dat_close',{'datId':report['dat']['datId']});report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['nativeArtifactsUnchanged']=hashes=={n:sha256(job/n) for n in hashes};report['passed']=report['passed'] and report['nativeArtifactsUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error'),'nativeArtifactsUnchanged':report['nativeArtifactsUnchanged']}),flush=True)
asyncio.run(main())
