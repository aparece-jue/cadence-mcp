"""Actual native parser and MCP engine solve of frozen folded include references."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/flat-libraries-control-20261029';root.mkdir(exist_ok=False);inputs=root/'inputs';inputs.mkdir()
(inputs/'inner model.lib').write_text('.SUBCKT RHALF A B\nRHALF A B 1k\n.ENDS RHALF\n',encoding='utf-8');(inputs/'outer models.lib').write_text('.LIB "inner model.lib"\n',encoding='utf-8');source=inputs/'divider.cir';source.write_text('* folded nested library divider\n.LIB "outer models.lib"\nV1 IN 0 DC 5\nX1 IN OUT RHALF\nR2 OUT 0 1k\n.DC V1 0 5 1\n.PROBE V([OUT])\n.END\n',encoding='utf-8')
before={p.name:sha256(p) for p in inputs.iterdir()};(root/'expected.json').write_text(json.dumps({'files':3,'sample':{'row':5,'trace':'V(OUT)','real':2.5,'absoluteTolerance':1e-6},'sourceHashes':before},indent=2)+'\n',encoding='utf-8');oracle=sha256(root/'expected.json')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(inputs,),60);raw=root/'raw-native';raw.mkdir()
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'check_pspice_input.tcl',cfg.install_root,source,raw,ADAPTERS/'json.tcl'],inputs,process_env(cfg),60)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(root/'work'),'--read-root',str(inputs),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'fullP02Accepted':False,'rawNativeProcess':process}
 try:
  assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content;return result.structured_content['data']
   prepared=await call('pspice_prepare',{'sourceCircuit':str(source),'inputEncoding':'preserve-bytes'});assert prepared['fileCount']==3
   plan=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'dc','expectedSamples':[{'block':0,'row':5,'traceName':'V(OUT)','real':2.5,'absoluteTolerance':1e-6,'relativeTolerance':0.0}]});key={k:plan[k] for k in ('planId','planDigest')};result=await call('pspice_apply_run',{**key,'idempotencyKey':'folded-divider'});assert result['numericalAcceptanceVerified'] and result['jobAssociationVerified'];report.update(plan=key,result=result)
   again=await call('pspice_apply_run',{**key,'idempotencyKey':'folded-divider'});assert not again['mutationReplayed'];report.update(passed=True,preparedThreeFileClosureAccepted=True,freshDc2_5VAccepted=True,idempotenceAccepted=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourcesUnchanged']=all(sha256(inputs/name)==h for name,h in before.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourcesUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['result'] }),flush=True)
raise SystemExit(asyncio.run(main()))
