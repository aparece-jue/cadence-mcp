"""Real MCP negative solver cases, retained historical failure and fresh observations."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/solver-diagnostics-mcp-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
old=repo/'.local/solver-diagnostics-probe-20261025'
for source in (old/'sources').glob('*.cir'):(sources/source.name).write_bytes(source.read_bytes())
(sources/'valid.cir').write_text('* independent valid divider\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE\n.END\n',encoding='ascii')
before={p.name:sha256(p) for p in sources.iterdir()}
expected={'nonconvergence':{'code':'pspice_nonconvergence','category':'nonconvergence','returnCode':0},'undefined-model':{'code':'pspice_output_error','category':'missing_model','returnCode':1},'voltage-loop':{'code':'pspice_output_error','category':'topology_error','returnCode':1}}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
def parameters(work,read):return StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(work),'--read-root',str(read),'--timeout-seconds','60'],env=env)
params=parameters(root/'work',sources);report={'passed':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==167;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content)
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   for name,want in expected.items():
    prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))});plan=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'dc'})
    key={k:plan[k] for k in ('planId','planDigest')};keys.append(key)
    result=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':name});assert result.is_error and result.structured_content['error']['code']==want['code'],result.structured_content
    inspection=await call('pspice_inspect_run_failure',key)
    assert inspection['workerStoppedVerified'] and inspection['inputClosureMatchesPlan'] and not inspection['solverSuccessVerified'] and not inspection['canReplayMutation']
    assert inspection['process']['returnCode']==want['returnCode'] and inspection['process']['remainingOwnedProcesses']==0
    assert inspection['output']['hasErrorDiagnostics'] and inspection['output']['diagnosticSummary']['errorCategories']==[want['category']]
    assert not inspection['output']['diagnosticSummary']['timeoutIsLicenseEvidence']
    r=await client.call_tool('pspice_open_run_dat',key);assert r.is_error and r.structured_content['error']['code']=='output_unverified'
    r=await client.call_tool('pspice_recover_run',key);assert r.is_error and r.structured_content['error']['code']==want['code']
    r=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':name});assert r.is_error and r.structured_content['error']['code']=='write_not_replayed'
    report['cases'].append({'case':name,'plan':plan,'inspection':inspection});print(name,want['category'],'passed',flush=True)
   valid=await call('pspice_prepare',{'sourceCircuit':str(sources/'valid.cir')})
   pending=await call('pspice_plan_run',{'simulationId':valid['simulationId'],'analysis':'dc'});key={k:pending[k] for k in ('planId','planDigest')};await call('pspice_cancel_run',key)
   inspected=await call('pspice_inspect_run_failure',key);assert inspected['workerNotStarted'] and not inspected['workerStoppedVerified'] and not inspected['observedFiles']
   report['checks']['pending_cancel_no_fabricated_evidence']=True
   timeout=await call('pspice_plan_run',{'simulationId':valid['simulationId'],'analysis':'dc','timeoutSeconds':1});key={k:timeout[k] for k in ('planId','planDigest')}
   r=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':'timeout'});assert r.is_error and r.structured_content['error']['code']=='timeout'
   inspection=await call('pspice_inspect_run_failure',key);assert inspection['recordedError']['code']=='timeout' and not inspection['solverSuccessVerified']
   assert not inspection['output'] or 'license_unavailable' not in inspection['output']['diagnosticSummary']['errorCategories']
   report['timeout']=inspection;report['checks']['timeout_not_invented_license_failure']=True
   bad=await client.call_tool('pspice_inspect_run_failure',{**keys[0],'planDigest':'0'*64});assert bad.is_error and bad.structured_content['error']['code']=='plan_digest_mismatch'
   report['checks']['digest_binding']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for key,case in zip(keys,report['cases']):
    r=await fresh.call_tool('pspice_inspect_run_failure',key);assert not r.is_error and r.structured_content['data']['observedFiles']==case['inspection']['observedFiles']
  report['checks']['fresh_failed_observation_no_mutation']=True
  # Historical exit0 nonconvergence was rejected only at DAT validation; inspect without rerunning.
  historical=json.loads((old/'report.json').read_text(encoding='utf-8'))['cases'][0];key={k:historical['plan'][k] for k in ('planId','planDigest')}
  async with Client(parameters(old/'work',old/'sources'),mode='legacy',read_timeout_seconds=180) as fresh:
   r=await fresh.call_tool('pspice_inspect_run_failure',key);assert not r.is_error
   d=r.structured_content['data'];assert d['recordedError']['code']=='unexpected_simulation_data' and d['output']['diagnosticSummary']['errorCategories']==['nonconvergence'];report['historicalObservation']=d
  report['checks']['historical_failure_retained_and_now_classified']=True
  report['checks']['source_and_oracle_unchanged']=before=={p.name:sha256(p) for p in sources.iterdir()} and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
