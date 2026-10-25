"""Actual MCP official CLI run acceptance with original electrical oracles."""
import asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/cli-runs-mcp-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
(sources/'dc.cir').write_bytes((repo/'.local/pspice-owned-7797dd67a5/source/divider.cir').read_bytes())
for name in ('ac','transient'):(sources/(name+'.cir')).write_bytes((repo/'.local/named-selectors-mcp-20261025/sources'/('wrapped-'+name+'.cir')).read_bytes())
(sources/'bad.cir').write_bytes((repo/'.local/solver-diagnostics-probe-20261025/sources/undefined-model.cir').read_bytes())
before={p.name:sha256(p) for p in sources.iterdir()};expected={'dc':2.5,'acReal':0.5,'acImaginary':-0.5,'absoluteTolerance':1e-6,'tauSeconds':0.001,'transientAbsoluteTolerance':2e-4,'tauRelativeTolerance':0.01};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==178;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   prepared={name:await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))}) for name in ('dc','ac','transient','bad')}
   for name in ('dc','ac','transient'):
    point={'block':0,'row':1 if name=='ac' else 0,'traceName':'V(2)' if name=='dc' else 'V(OUT)','real':2.5 if name=='dc' else 0.5 if name=='ac' else 0.0,'imaginary':-0.5 if name=='ac' else None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}
    plan=await call('pspice_plan_cli_run',{'simulationId':prepared[name]['simulationId'],'analysis':name,'expectedSamples':[point]});key={k:plan[k] for k in ('planId','planDigest')};assert plan['preview']['backend']=='official_psp_cmd_r'
    result=await call('pspice_apply_cli_run',{**key,'idempotencyKey':name});assert result['backend']=='official_psp_cmd_r' and result['numericalAcceptanceVerified'] and result['numericalAcceptanceScope']=='declared_trace_rows_only' and 'cli_backend' not in result['notChecked']
    opened=await call('pspice_open_run_dat',{**key,'backend':'cli'});assert opened['jobAssociationVerified'] and opened['producedByPlan']==key['planId']
    out=await call('pspice_inspect_run_output',{**key,'backend':'cli'});assert out['jobAssociationVerified'] and not out['hasErrorDiagnostics']
    directory=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+key['planId']);manifest=json.loads((directory/'run-artifacts.json').read_text(encoding='utf-8'));assert manifest['backend']=='official_psp_cmd_r' and manifest['nativeOutputIdentityVerified']
    assert sha256(directory/'input.out')==sha256(directory/'result.out') and sha256(directory/'input.dat')==sha256(directory/'result.dat')
    row={'case':name,'plan':plan,'result':result,'manifest':manifest};report['cases'].append(row)
    if name=='transient':
     times=(await call('pspice_dat_samples',{'datId':opened['datId'],'block':0,'traceName':'Time','offset':0,'limit':1000}))['items'];values=(await call('pspice_dat_samples',{'datId':opened['datId'],'block':0,'traceName':'V(OUT)','offset':0,'limit':1000}))['items'];assert len(times)==len(values)>500
     pairs=[(t['real'],v['real']) for t,v in zip(times,values)];errors=[abs(v-(1-math.exp(-t/0.001))) for t,v in pairs];assert max(errors)<=2e-4
     threshold=1-math.exp(-1);cross=None
     for (ta,va),(tb,vb) in zip(pairs,pairs[1:]):
      if va<=threshold<=vb and vb>va:cross=ta+(tb-ta)*(threshold-va)/(vb-va);break
     assert cross is not None and abs(cross/0.001-1)<=0.01;row.update(sampleCount=len(values),maxAbsoluteError=max(errors),observedTauSeconds=cross)
    keys.append((name,key));await call('pspice_dat_close',{'datId':opened['datId']});print(name,'CLI numeric oracle passed',flush=True)
   bad=await call('pspice_plan_cli_run',{'simulationId':prepared['bad']['simulationId'],'analysis':'dc'});key={k:bad[k] for k in ('planId','planDigest')}
   r=await client.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':'bad'});assert r.is_error and r.structured_content['error']['code']=='pspice_output_error',r.structured_content
   failure=await call('pspice_inspect_run_failure',{**key,'kind':'cli'});assert failure['output']['hasErrorDiagnostics'] and failure['workerStoppedVerified'];report['bad']=failure
   r=await client.call_tool('pspice_open_run_dat',{**key,'backend':'cli'});assert r.is_error and r.structured_content['error']['code']=='output_unverified';report['checks']['bad_native_input_not_opened_as_success']=True
   pending=await call('pspice_plan_cli_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc'});key={k:pending[k] for k in ('planId','planDigest')};await call('pspice_cancel_cli_run',key)
   r=await client.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':'pending'});assert r.is_error;report['checks']['pending_cli_cancel']=True
   jobs=await call('pspice_cli_run_jobs',{'offset':0,'limit':100});assert jobs['total']==5
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for name,key in keys:
    r=await fresh.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':name});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    r=await fresh.call_tool('pspice_recover_cli_run',key);assert not r.is_error
    r=await fresh.call_tool('pspice_open_run_dat',{**key,'backend':'cli'});assert not r.is_error
  report['checks']['fresh_lifecycle_no_replay']=True;report['checks']['source_oracle_unchanged']=before=={p.name:sha256(p) for p in sources.iterdir()} and sha256(root/'expected.json')==oracle
  report['passed']=len(report['cases'])==3 and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
