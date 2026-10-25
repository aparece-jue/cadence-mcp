"""Actual new mixed solve, typed analog partition, and refusal of misleading digital numeric data."""
import argparse,asyncio,json,os,shutil,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256,write_json
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-circuit'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);inputs=root/'inputs';inputs.mkdir();source=inputs/'mixed.cir';shutil.copyfile(a.source_circuit,source);before=sha256(source)
expected={'analysis':'transient','analogVolts':1.0,'loadAmps':0.001,'supplyVolts':5.0,'endSeconds':4e-6,'absoluteTolerance':1e-6,'digitalExpectedRowCount':5,'digitalStatesAcceptance':False}
write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(inputs),'--timeout-seconds','60'],env=os.environ.copy())
async def main():
 report={'passed':False,'scope':'mixed analog rows and plan/OUT/DAT association; digital logic values remain unverified and refused','checks':{}}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==155;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,(name,result.structured_content)
    Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
   prepared=await call('pspice_prepare',{'sourceCircuit':str(source)});simulation=prepared['simulationId']
   wanted=[{'block':0,'row':0,'traceName':name,'real':value,'absoluteTolerance':1e-6} for name,value in [('V(ANALOG)',1.0),('I(RLOAD)',0.001),('V(DPWR)',5.0)]]
   plan=await call('pspice_plan_run',{'simulationId':simulation,'analysis':'transient','expectedSamples':wanted});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   result=await call('pspice_apply_run',{**key,'idempotencyKey':'mixed-analog'});report['result']=result
   assert result['numericalAcceptanceVerified'] and result['jobAssociationVerified'] and result['designPassed'] is None
   opened=await call('pspice_open_run_dat',key);ident=opened['datId'];report['opened']=opened
   assert opened['solverSuccessVerified'] and opened['jobAssociationVerified'] and opened['producedByPlan']==key['planId']
   block=(await call('pspice_dat_query',{'datId':ident,'entity':'block'}))['items'][0];report['block']=block
   assert block['dataTypeCode']==2 and block['analogReadSupported'] and not block['digitalReadSupported']
   assert block['analogRowCount']>0 and block['digitalRowCount']==5 and block['digitalTraceCount']==1
   traces=(await call('pspice_dat_query',{'datId':ident,'entity':'trace','block':0,'limit':1000}))['items'];logic=next(t for t in traces if t['name']=='DIN');assert logic['signalType']=='digital' and logic['rowCount']==5 and not logic['sampleReadSupported']
   observed={}
   for name,value in [('V(ANALOG)',1.0),('I(RLOAD)',0.001),('V(DPWR)',5.0)]:
    samples=await call('pspice_dat_samples',{'datId':ident,'block':0,'traceName':name,'limit':1000})
    assert samples['jobAssociationVerified'] and samples['producedByPlan']==key['planId']
    assert len(samples['items'])==block['analogRowCount'] and all(abs(s['real']-value)<=1e-6 and s['imaginary'] is None for s in samples['items'])
    observed[name]=samples
   times=await call('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'Time','limit':1000});axis=[v['real'] for v in times['items']];assert axis[0]==0 and abs(axis[-1]-4e-6)<=1e-12 and all(a<b for a,b in zip(axis,axis[1:]))
   measured=await call('pspice_dat_measure',{'datId':ident,'block':0,'traceName':'V(ANALOG)'});assert abs(measured['sampleMean']-1)<=1e-6 and measured['jobAssociationVerified']
   report['observed']=observed;report['measurement']=measured;report['checks']['new_mixed_solve_analog_rows_and_formal_association']=True
   for tool in ('pspice_dat_samples','pspice_dat_measure'):
    denied=await client.call_tool(tool,{'datId':ident,'block':0,'traceName':'DIN'});assert denied.is_error and denied.structured_content['error']['code']=='capability_unavailable'
   report['checks']['logic_not_decoded_using_analog_row_count']=True
   await call('pspice_dat_close',{'datId':ident})
   wrong=await call('pspice_plan_run',{'simulationId':simulation,'analysis':'transient','expectedSamples':[{**wanted[0],'real':2.0}]});wk={k:wrong[k] for k in ('planId','planDigest')}
   failed=await client.call_tool('pspice_apply_run',{**wk,'idempotencyKey':'wrong-analog'});assert failed.is_error and failed.structured_content['error']['code']=='simulation_expectation_mismatch'
   assert (await client.call_tool('pspice_open_run_dat',wk)).is_error
   refused=await call('pspice_plan_run',{'simulationId':simulation,'analysis':'transient','expectedSamples':[{'block':0,'row':0,'traceName':'DIN','real':0.0,'absoluteTolerance':1e-6}]});dk={k:refused[k] for k in ('planId','planDigest')}
   failed=await client.call_tool('pspice_apply_run',{**dk,'idempotencyKey':'logic-not-certified'});assert failed.is_error and failed.structured_content['error']['code']=='capability_unavailable'
   assert (await client.call_tool('pspice_open_run_dat',dk)).is_error
   failed=await client.call_tool('pspice_apply_run',{**dk,'idempotencyKey':'logic-not-certified'});assert failed.is_error and failed.structured_content['error']['code']=='write_not_replayed'
   report['checks']['wrong_analog_and_unsupported_logic_oracles_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   applied=await fresh.call_tool('pspice_apply_run',{**key,'idempotencyKey':'mixed-analog'});assert not applied.is_error and applied.structured_content['data']['mutationReplayed'] is False
   recovered=await fresh.call_tool('pspice_recover_run',key);assert not recovered.is_error
   opened=await fresh.call_tool('pspice_open_run_dat',key);assert not opened.is_error;ident=opened.structured_content['data']['datId']
   sample=await fresh.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'I(RLOAD)','limit':1});assert not sample.is_error and sample.structured_content['data']['jobAssociationVerified'] and abs(sample.structured_content['data']['items'][0]['real']-0.001)<=1e-6
   report['checks']['fresh_recovery_no_replay_and_association']=True
  report['checks']['source_and_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
