"""Real MCP byte-preserving CLI pipeline compatibility; original divider oracle, not native nominal-library acceptance."""
import asyncio,cmath,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];root=r/'.local/preserved-cli-mcp-v2-20261026';root.mkdir(exist_ok=False);source=root/'divider.cir';original=r/'.local/pspice-owned-7797dd67a5/source/divider.cir';title,sep,body=original.read_bytes().partition(b'\n');source.write_bytes(title+sep+b'* opaque legacy comment \x81E\r\n'+body);install=Path(r'D:\Program Files\Cadence\SPB_24.1');library=install/'tools/pspice/library';before=sha256(source)
expected=[{'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}]
(root/'expected.json').write_text(json.dumps({'scope':'Unchanged original divider2.5V oracle, opaque comment only','expectedSamples':expected},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(library),'--timeout-seconds','120'],env=env);report={'passed':False,'sourceBefore':before,'oracleSha256':oracle}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    value=await client.call_tool(name,args)
    if value.is_error:raise AssertionError((name,value.structured_content))
    return value.structured_content['data']
   report['prepared']=await call('pspice_prepare',{'sourceCircuit':str(source),'inputEncoding':'preserve-bytes','inputBudget':'extended'});assert report['prepared']['fileCount']==1
   report['plan']=await call('pspice_plan_cli_run',{'simulationId':report['prepared']['simulationId'],'analysis':'dc','expectedSamples':expected});key={k:report['plan'][k] for k in ('planId','planDigest')};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   report['result']=await call('pspice_apply_cli_run',{**key,'idempotencyKey':'preserved-divider-dc'});assert report['result']['numericalAcceptanceVerified'];report['output']=await call('pspice_inspect_run_output',{**key,'backend':'cli'});assert not report['output']['hasErrorDiagnostics'];report['dat']=await call('pspice_open_run_dat',{**key,'backend':'cli'});assert report['dat']['jobAssociationVerified'];await call('pspice_dat_close',{'datId':report['dat']['datId']})
   report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceAndOracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error'),'prepared':report.get('prepared')}),flush=True)
asyncio.run(main())
