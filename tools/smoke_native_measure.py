"""Actual MCP complete-analysis native .MEASURE acceptance against independent expectations."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/native-measure-mcp-v2-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
old=repo/'.local/native-measure-20261023'
for name in ('dc','ac','transient'):(sources/(name+'.cir')).write_bytes((old/name/'input.cir').read_bytes())
(sources/'ac-good.cir').write_text((sources/'ac.cir').read_text().replace('VM(2)','V(2)'),encoding='ascii')
hashes={p.name:sha256(p) for p in sources.iterdir()}
def exp(name,field,value,tolerance=1e-6):return {'name':name,'field':field,'expected':value,'absoluteTolerance':tolerance,'relativeTolerance':0.0}
expected={'dc':[exp('divider_max','value',2.5),exp('divider_avg','value',1.25),exp('divider_at','value',2.0),exp('divider_at','at',4.0)],'transient':[exp('rc_tau','at',0.001,1e-5),exp('rc_at','value',0.632120558829,1e-5)],'ac-good':[exp('rc_mag','value',2**-0.5,1e-5)]}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==166;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content)
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   prepared={name:await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))}) for name in ('dc','transient','ac-good','ac')}
   for name,checks in expected.items():
    analysis='ac' if name=='ac-good' else name
    plan=await call('pspice_plan_measure_run',{'simulationId':prepared[name]['simulationId'],'analysis':analysis,'expectedMeasurements':checks})
    key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key))
    result=await call('pspice_apply_measure_run',{**key,'idempotencyKey':name})
    assert result['nativeCompletionVerified'] and result['independentDatReadVerified'] and result['numericalAcceptanceVerified'] and result['numericalAcceptanceScope']=='declared_native_measurement_fields_only'
    inspection=await call('pspice_inspect_run_measurements',key)
    assert inspection['nativeMeasurementChecks'] and inspection['designPassed'] is None
    assert {r['name'].casefold() for r in inspection['nativeMeasurements']}=={r['name'].casefold() for r in plan['preview']['measurementDeclarations']}
    report['cases'].append({'case':name,'plan':plan,'result':result,'inspection':inspection});print(name,'passed',flush=True)
   bad=await call('pspice_plan_measure_run',{'simulationId':prepared['ac']['simulationId'],'analysis':'ac','expectedMeasurements':expected['ac-good']})
   key={k:bad[k] for k in ('planId','planDigest')}
   r=await client.call_tool('pspice_apply_measure_run',{**key,'idempotencyKey':'failed-evaluation'})
   assert r.is_error and r.structured_content['error']['code']=='pspice_output_error',r.structured_content
   refused=await client.call_tool('pspice_inspect_run_measurements',key);assert refused.is_error and refused.structured_content['error']['code']=='output_unverified'
   replay=await client.call_tool('pspice_apply_measure_run',{**key,'idempotencyKey':'failed-evaluation'});assert replay.is_error and replay.structured_content['error']['code']=='write_not_replayed'
   report['checks']['failed_evaluation_not_numeric_success']=True
   wrong=await call('pspice_plan_measure_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc','expectedMeasurements':[exp('divider_max','value',3.0)]})
   key={k:wrong[k] for k in ('planId','planDigest')};r=await client.call_tool('pspice_apply_measure_run',{**key,'idempotencyKey':'wrong'})
   assert r.is_error and r.structured_content['error']['code']=='measurement_expectation_mismatch',r.structured_content
   report['checks']['wrong_independent_expectation_refused']=True
   pending=await call('pspice_plan_measure_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc','expectedMeasurements':expected['dc']})
   key={k:pending[k] for k in ('planId','planDigest')};await call('pspice_cancel_measure_run',key)
   r=await client.call_tool('pspice_apply_measure_run',{**key,'idempotencyKey':'pending'});assert r.is_error
   report['checks']['pending_cancel_refused']=True
   jobs=await call('pspice_measure_run_jobs',{'offset':0,'limit':100});assert jobs['total']==6
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for name,key in keys:
    r=await fresh.call_tool('pspice_apply_measure_run',{**key,'idempotencyKey':name});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    r=await fresh.call_tool('pspice_recover_measure_run',key);assert not r.is_error
    r=await fresh.call_tool('pspice_inspect_run_measurements',key);assert not r.is_error
  report['checks']['fresh_lifecycle_without_replay']=True
  report['checks']['source_and_oracle_unchanged']=hashes=={p.name:sha256(p) for p in sources.iterdir()} and sha256(root/'expected.json')==oracle
  report['passed']=len(report['cases'])==3 and all(report['checks'].values())
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
