"""Fresh public MCP P03 numeric/diagnostic/measurement acceptance; input and math frozen first."""
import argparse,asyncio,json,math,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();repo=Path(__file__).resolve().parents[1]
source_paths={'dc':repo/'.local/pspice-owned-7797dd67a5/source/divider.cir','transient':repo/'.local/named-selectors-mcp-20261025/sources/wrapped-transient.cir'}
for name,path in source_paths.items():(sources/(name+'.cir')).write_bytes(path.read_bytes())
(sources/'ac.cir').write_text('Independent wideband RC response\nV1 IN 0 DC 0 AC 1\nR1 IN OUT 1k\nC1 OUT 0 1u\n.AC DEC 60 1 100k\n.PROBE V([IN]) V([OUT])\n.END\n',encoding='ascii')
for name in ('dc','transient','ac'):
 text=(repo/'.local/native-measure-20261023'/name/'input.cir').read_text(encoding='ascii')
 if name=='ac':text=text.replace('VM(2)','V(2)')
 (sources/('measure-'+name+'.cir')).write_text(text,encoding='ascii')
for name in ('nonconvergence','undefined-model','voltage-loop'):(sources/(name+'.cir')).write_bytes((repo/'.local/solver-diagnostics-probe-20261025/sources'/(name+'.cir')).read_bytes())
def check(name,field,value,tol=1e-6):return {'name':name,'field':field,'expected':value,'absoluteTolerance':tol,'relativeTolerance':0.0}
native={'dc':[check('divider_max','value',2.5),check('divider_avg','value',1.25),check('divider_at','value',2),check('divider_at','at',4)],'transient':[check('rc_tau','at',.001,1e-5),check('rc_at','value',1-math.exp(-1),1e-5)],'ac':[check('rc_mag','value',2**-.5,1e-5)]}
oracle={'dcVoltage':2.5,'dcAbsoluteTolerance':1e-6,'tauSeconds':.001,'cutoffHz':1/(2*math.pi*.001),'tauAndCutoffRelativeTolerance':.01,'transientWholeCurveAbsoluteTolerance':2e-4,'acWholeComplexComponentTolerance':1e-6,'nativeMeasurements':native,'diagnostics':{'nonconvergence':['pspice_nonconvergence','nonconvergence',0],'undefined-model':['pspice_output_error','missing_model',1],'voltage-loop':['pspice_output_error','topology_error',1]}}
(root/'expected.json').write_text(json.dumps(oracle,indent=2),encoding='utf-8');before={path.name:sha256(path) for path in sources.iterdir()};oracle_hash=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'measurements':[],'runs':[],'diagnostics':[],'checks':{}}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;report['tools']=len(tools);schemas={t.name:t.output_schema for t in tools}
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   prepared={path.stem:await call('pspice_prepare',{'sourceCircuit':str(path)}) for path in sources.iterdir()}
   for analysis,checks in native.items():
    plan=await call('pspice_plan_measure_run',{'simulationId':prepared['measure-'+analysis]['simulationId'],'analysis':analysis,'expectedMeasurements':checks});key={k:plan[k] for k in ('planId','planDigest')};result=await call('pspice_apply_measure_run',{**key,'idempotencyKey':analysis});inspection=await call('pspice_inspect_run_measurements',key);assert result['nativeCompletionVerified'] and result['independentDatReadVerified'] and result['numericalAcceptanceVerified']
    units=inspection['measurementUnits'];assert not units['nativeUnitMetadataAvailable'] and units['unknownUnitFieldCount']==0
    axis='V' if analysis=='dc' else 's' if analysis=='transient' else 'Hz';assert units['analysisAxis']['unit']==axis
    for measured in inspection['nativeMeasurements']:
     assert measured['fieldUnits']['value']['unit']=='V'
     for field in ('at','from','to'):
      if field in measured['fields']:assert measured['fieldUnits'][field]['unit']==axis
    directory=root/'work/isolated-jobs/pspice_measure_run'/('plan-'+key['planId']);manifest=json.loads((directory/'run-artifacts.json').read_text(encoding='utf-8'));assert [{k:v for k,v in row.items() if k!='fieldUnits'} for row in inspection['nativeMeasurements']]==manifest['nativeMeasurements']
    report['measurements'].append({'analysis':analysis,'plan':plan,'result':result,'inspection':inspection,'manifestHash':sha256(directory/'run-artifacts.json')});dump();print('native_measure',analysis,'passed',flush=True)
   for backend in ('engine','cli'):
    for analysis in ('dc','transient','ac'):
     if analysis=='dc':sample={'traceName':'V(2)','row':0,'real':2.5,'absoluteTolerance':1e-6}
     elif analysis=='transient':sample={'traceName':'V(OUT)','row':0,'real':0.0,'absoluteTolerance':1e-6}
     else:
      x=2*math.pi*.001;sample={'traceName':'V(OUT)','row':0,'real':1/(1+x*x),'imaginary':-x/(1+x*x),'absoluteTolerance':1e-6}
     prefix='pspice_plan_run' if backend=='engine' else 'pspice_plan_cli_run';apply='pspice_apply_run' if backend=='engine' else 'pspice_apply_cli_run';plan=await call(prefix,{'simulationId':prepared[analysis]['simulationId'],'analysis':analysis,'expectedSamples':[sample]});key={k:plan[k] for k in ('planId','planDigest')};result=await call(apply,{**key,'idempotencyKey':backend+'-'+analysis});opened=await call('pspice_open_run_dat',{**key,'backend':backend});assert opened['jobAssociationVerified'] and opened['producedByPlan']==key['planId'];out=await call('pspice_inspect_run_output',{**key,'backend':backend});assert out['jobAssociationVerified'] and not out['hasErrorDiagnostics']
     async def samples(name):
      page=await call('pspice_dat_samples',{'datId':opened['datId'],'block':0,'traceName':name,'offset':0,'limit':1000});assert page['nextOffset'] is None and page['jobAssociationVerified'] and page['producedByPlan']==key['planId'];return page
     voltage=await samples('V(2)' if analysis=='dc' else 'V(OUT)');assert voltage['unit']=='V';row={'backend':backend,'analysis':analysis,'plan':plan,'result':result,'output':out,'rows':len(voltage['items'])}
     if analysis=='dc':assert all(abs(v['real']-2.5)<=1e-6 for v in voltage['items']);row['maxAbsoluteError']=max(abs(v['real']-2.5) for v in voltage['items'])
     else:
      axis=await samples('Time' if analysis=='transient' else 'Frequency');assert axis['unit']==('s' if analysis=='transient' else 'Hz');assert len(axis['items'])==len(voltage['items'])
      if analysis=='transient':
       errors=[abs(v['real']-(1-math.exp(-t['real']/.001))) for t,v in zip(axis['items'],voltage['items'])];assert len(errors)>500 and max(errors)<=2e-4
       cross=await call('pspice_dat_measure',{'datId':opened['datId'],'block':0,'traceName':'V(OUT)','measurement':'first_crossing','threshold':1-math.exp(-1),'direction':'rising'});assert cross['found'] and abs(cross['axisValue']/.001-1)<=.01;row.update(maxAbsoluteError=max(errors),observedTau=cross['axisValue'])
      else:
       errors=[]
       for f,v in zip(axis['items'],voltage['items']):
        x=2*math.pi*f['real']*.001;errors.extend([abs(v['real']-1/(1+x*x)),abs(v['imaginary']+x/(1+x*x))])
       assert len(voltage['items'])>=300 and max(errors)<=1e-6
       cross=await call('pspice_dat_measure',{'datId':opened['datId'],'block':0,'traceName':'V(OUT)','measurement':'first_crossing','component':'magnitude','threshold':2**-.5,'direction':'falling'});assert cross['found'] and abs(cross['axisValue']/oracle['cutoffHz']-1)<=.01;row.update(maxComplexComponentError=max(errors),observedCutoff=cross['axisValue'])
     await call('pspice_dat_close',{'datId':opened['datId']});report['runs'].append(row);dump();print(backend,analysis,'numeric passed',flush=True)
   for name,(code,category,exit_code) in oracle['diagnostics'].items():
    plan=await call('pspice_plan_run',{'simulationId':prepared[name]['simulationId'],'analysis':'dc'});key={k:plan[k] for k in ('planId','planDigest')};await call('pspice_apply_run',{**key,'idempotencyKey':name},code);failed=await call('pspice_inspect_run_failure',key);assert failed['workerStoppedVerified'] and failed['process']['returnCode']==exit_code and failed['process']['remainingOwnedProcesses']==0 and failed['output']['diagnosticSummary']['errorCategories']==[category];await call('pspice_open_run_dat',key,'output_unverified');report['diagnostics'].append({'case':name,'plan':plan,'failure':failed});dump();print(name,'failure classified',flush=True)
   wrong=await call('pspice_plan_measure_run',{'simulationId':prepared['measure-dc']['simulationId'],'analysis':'dc','expectedMeasurements':[check('divider_max','value',3)]});key={k:wrong[k] for k in ('planId','planDigest')};await call('pspice_apply_measure_run',{**key,'idempotencyKey':'wrong-oracle'},'measurement_expectation_mismatch');await call('pspice_inspect_run_measurements',key,'output_unverified');report['checks']['wrong_independent_measurement_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for row in report['measurements']:
    key={k:row['plan'][k] for k in ('planId','planDigest')};response=await fresh.call_tool('pspice_inspect_run_measurements',key);assert not response.is_error and response.structured_content['data']==row['inspection'];directory=root/'work/isolated-jobs/pspice_measure_run'/('plan-'+key['planId']);assert sha256(directory/'run-artifacts.json')==row['manifestHash']
   for row in report['runs']:
    key={k:row['plan'][k] for k in ('planId','planDigest')};name='pspice_apply_run' if row['backend']=='engine' else 'pspice_apply_cli_run';response=await fresh.call_tool(name,{**key,'idempotencyKey':row['backend']+'-'+row['analysis']});assert not response.is_error and not response.structured_content['data']['mutationReplayed']
  report['checks'].update(fresh_units_are_readonly_projection=True,all_six_runs_not_replayed=True,native_exit_zero_nonconvergence_not_success=True)
  report['sourceHashesAfter']={path.name:sha256(path) for path in sources.iterdir()};report['sourceHashesBefore']=before;report['expectedHashAfter']=sha256(root/'expected.json');report['expectedHashBefore']=oracle_hash;assert report['sourceHashesAfter']==before and report['expectedHashAfter']==oracle_hash;report['passed']=len(report['measurements'])==3 and len(report['runs'])==6 and len(report['diagnostics'])==3 and all(report['checks'].values())
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 dump();print(json.dumps({'passed':report['passed'],'measurements':len(report['measurements']),'runs':len(report['runs']),'diagnostics':len(report['diagnostics']),'error':report.get('error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
