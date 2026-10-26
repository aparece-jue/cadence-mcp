import argparse,asyncio,json,os,sys,shutil
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser(description='Actual MCP before/after solver and old-DAT refusal for the LowPassFilters resistor iteration.')
for name in ('native-inputs-root','oracle','workspace-root','install-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];inputs=a.native_inputs_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);oracle_path=a.oracle.resolve(strict=True);
oracle=json.loads(oracle_path.read_text());oracle_hash=sha256(oracle_path);native=json.loads((inputs/'report.json').read_text());assert native['passed'];sources={label:Path(row['circuit']) for label,row in native['cases'].items()};before={str(p):sha256(p) for p in inputs.rglob('*') if p.is_file()};report={'passed':False,'fullP05Accepted':False,'scope':'Actual resistor iteration using MCP property edit, fixed authenticated native NET/ALS helper, native CIR and MCP CLI; formal native-generation MCP tasks remain','oracleSha256':oracle_hash,'cases':{}}
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(inputs),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as c:
   async def call(name,args):
    out=await c.call_tool(name,args)
    if out.is_error:raise AssertionError((name,out.structured_content))
    return out.structured_content['data']
   prior_dat=None
   for label in ['before','after']:
    entry={'sourceCircuitSha256':sha256(sources[label]),'sourceDesignSha256':native['cases'][label]['sourceDesignSha256']};report['cases'][label]=entry
    opened=await call('pspice_prepare',{'sourceCircuit':str(sources[label])});assert opened['fileCount']==4;entry['prepared']=opened
    args={'simulationId':opened['simulationId'],'analysis':'ac','expectedSamples':oracle['cases'][label]}
    if label=='after':
     stale=await call('pspice_plan_cli_run',args);key={k:stale[k] for k in ['planId','planDigest']};d=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+key['planId']);shutil.copyfile(prior_dat,d/'input.dat');stale_hash=sha256(d/'input.dat')
     out=await c.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':'p05-old-before-dat-must-not-run'});report['staleOutputRejection']=out.structured_content;assert out.is_error and out.structured_content['error']['code']=='preexisting_cli_output'
     row=json.loads((d/'plan.json').read_text());assert row['state']=='failed' and not row.get('workerPid') and not (d/'input.cir').exists() and not (d/'cli-receipt.json').exists() and sha256(d/'input.dat')==stale_hash;report['staleWorkerNotStarted']=True
    plan=await call('pspice_plan_cli_run',args);entry['plan']=plan;key={k:plan[k] for k in ['planId','planDigest']};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    result=await call('pspice_apply_cli_run',{**key,'idempotencyKey':'p05-fresh-'+label});entry['result']=result;assert result['numericalAcceptanceVerified']
    output=await call('pspice_inspect_run_output',{**key,'backend':'cli'});assert not output['hasErrorDiagnostics'];entry['output']=output
    dat=await call('pspice_open_run_dat',{**key,'backend':'cli'});assert dat['jobAssociationVerified'];entry['dat']=dat;sid=dat['datId']
    entry['firstSample']=(await call('pspice_dat_samples',{'datId':sid,'block':0,'traceName':'V(N00509)','offset':0,'limit':1}))['items'][0];await call('pspice_dat_close',{'datId':sid})
    d=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+key['planId']);entry['nativeOutputHashes']={name:sha256(d/name) for name in ['input.dat','input.out','cli-receipt.json']};prior_dat=d/'input.dat'
    assert await call('pspice_apply_cli_run',{**key,'idempotencyKey':'p05-fresh-'+label})==result
   assert report['cases']['before']['firstSample']['real']-report['cases']['after']['firstSample']['real']>.16
   assert report['cases']['before']['prepared']['sourceFingerprint']!=report['cases']['after']['prepared']['sourceFingerprint'];report['voltageChangeAccepted']=True
   report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAndOracleUnchanged']=sha256(oracle_path)==oracle_hash and all(sha256(Path(p))==digest for p,digest in before.items());report['passed']=report['passed'] and report['sourceAndOracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ['passed','error','voltageChangeAccepted','staleWorkerNotStarted','sourceAndOracleUnchanged']}))
asyncio.run(main())

if not report["passed"]:raise SystemExit(1)
