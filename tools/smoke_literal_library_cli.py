"""Private MCP solver acceptance for literal circuit / entirely unused library template."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser();parser.add_argument('--workspace-root',type=Path,required=True);args=parser.parse_args();root=args.workspace_root.resolve();root.mkdir(parents=True,exist_ok=False);src=root/'source';src.mkdir();circuit=src/'divider.cir';lib=src/'unused.lib'
circuit.write_text('* own literal divider\n.LIB "unused.lib"\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE V(2)\n.END\n',encoding='utf-8')
lib.write_text('.SUBCKT UNUSED A B\nUROM A B ROM_MODEL FILE=|ROM_FILE|\n.ENDS UNUSED\n',encoding='utf-8')
source={p.name:sha256(p) for p in (circuit,lib)};report={'passed':False,'expectedVoltage':2.5,'sourceBefore':source};env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(src),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   async def call(name,args):
    out=await client.call_tool(name,args)
    if out.is_error:raise AssertionError((name,out.structured_content))
    return out.structured_content['data']
   report['prepared']=await call('pspice_prepare',{'sourceCircuit':str(circuit)})
   report['plan']=await call('pspice_plan_cli_run',{'simulationId':report['prepared']['simulationId'],'analysis':'dc','expectedSamples':[{'block':0,'row':0,'traceName':'V(2)','real':2.5,'absoluteTolerance':1e-6,'relativeTolerance':1e-6}]})
   key={k:report['plan'][k] for k in ('planId','planDigest')};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   report['result']=await call('pspice_apply_cli_run',{**key,'idempotencyKey':'literal-library-once'});assert report['result']['numericalAcceptanceVerified']
   report['output']=await call('pspice_inspect_run_output',{**key,'backend':'cli'});assert not report['output']['hasErrorDiagnostics'];report['dat']=await call('pspice_open_run_dat',{**key,'backend':'cli'});assert report['dat']['jobAssociationVerified'];await call('pspice_dat_close',{'datId':report['dat']['datId']});report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceUnchanged']={p.name:sha256(p) for p in (circuit,lib)}==source;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}),flush=True)
asyncio.run(main())
