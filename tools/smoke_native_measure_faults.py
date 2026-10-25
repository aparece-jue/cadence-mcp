"""Owned native .MEASURE failures and fresh MCP recovery without rerun."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_measurements import PSpiceMeasurementRuns
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.environment import process_env
repo=Path(__file__).resolve().parents[1];root=repo/'.local/native-measure-faults-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
source=sources/'divider.cir';source.write_bytes((repo/'.local/native-measure-20261023/dc/input.cir').read_bytes());before=sha256(source)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(sources,),60);inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];service=PSpiceMeasurementRuns(cfg,inputs,PSpiceDat(cfg));native=service.execute
expected=[{'name':'divider_max','field':'value','expected':2.5,'absoluteTolerance':1e-6,'relativeTolerance':0.0}]
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
report={'passed':False,'checks':{},'cases':[]}
def plan(**kw):return service.plan(sid,'dc',expected,**kw)
def apply(key,label):return service.apply(key['planId'],key['planDigest'],label)
def reject(action,code=None):
 try:action()
 except CadenceError as error:
  if code:assert error.code==code,(error.code,code)
  return error.code
 raise AssertionError('Unexpected acceptance')
def stopped(key):
 d,_,row=service._load(key['planId']);p=row['process'];assert p['remainingOwnedProcesses']==0 and p['rootExitSignalConfirmed'] and p['observedProcessExitSignalsConfirmed'];return d,row
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
async def main():
 try:
  key=plan();calls=[]
  def lose(d,p,cancel,started):
   calls.append(d);proc=native(d,p,cancel,started);assert proc['returnCode']==0;(d/'receipt.json').unlink();return proc
  service.execute=lose;error=reject(lambda:apply(key,'lost'));d,row=stopped(key);assert row['state']=='failed'
  hashes={name:sha256(d/name) for name in ('result.out','result.dat','input_measure.txt')}
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   assert len((await client.list_tools()).tools)==166
   args={k:key[k] for k in ('planId','planDigest')};r=await client.call_tool('pspice_recover_measure_run',args);assert not r.is_error,r.structured_content
   recovered=r.structured_content['data'];assert recovered['state']=='verified_recovered' and recovered['numericalAcceptanceVerified'] and not recovered['nativeCompletionVerified'] and not recovered['mutationReplayed']
   r=await client.call_tool('pspice_inspect_run_measurements',args);assert not r.is_error and not r.structured_content['data']['nativeCompletionVerified']
   r=await client.call_tool('pspice_apply_measure_run',{**args,'idempotencyKey':'lost'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
  assert len(calls)==1 and hashes=={n:sha256(d/n) for n in hashes}
  report['cases'].append({'case':'lost_receipt','plan':key,'error':error,'process':row['process'],'recovered':recovered});report['checks']['fresh_recovery_no_rerun']=True;print('receipt recovery passed',flush=True)
  service.execute=native;key=plan()
  def cancel_start(d,p,cancel,started):
   def ready(pid):started(pid);assert service.cancel(key['planId'],key['planDigest'])['cancelRequested']
   return native(d,p,cancel,ready)
  service.execute=cancel_start;reject(lambda:apply(key,'cancel'),'operation_cancelled');d,row=stopped(key);assert row['state']=='cancelled'
  report['cases'].append({'case':'active_cancel','plan':key,'process':row['process']});report['checks']['active_cancel_owned_zero']=True
  service.execute=native;key=plan(timeout_seconds=1);delay=root/'delay.tcl';delay.write_text('after 3000\nexit 2\n',encoding='ascii')
  def timeout(d,p,cancel,started):return run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',delay],d,process_env(cfg),p['timeoutSeconds'],cancel=cancel,on_started=started)
  service.execute=timeout;reject(lambda:apply(key,'timeout'),'timeout');d,row=stopped(key)
  report['cases'].append({'case':'timeout','plan':key,'process':row['process']});report['checks']['timeout_owned_zero']=True
  service.execute=native;key=plan()
  def poison(d,p,cancel,started):
   proc=native(d,p,cancel,started);assert proc['returnCode']==0
   path=d/'input_measure.txt';text=path.read_text(encoding='cp1252');assert '2.5000E+00' in text;path.write_text(text.replace('2.5000E+00','3.0000E+00'),encoding='cp1252');return proc
  service.execute=poison;reject(lambda:apply(key,'poison'),'measurement_expectation_mismatch');d,row=stopped(key)
  reject(lambda:service.recover(key['planId'],key['planDigest']),'measurement_expectation_mismatch');reject(lambda:apply(key,'poison'),'write_not_replayed')
  report['cases'].append({'case':'numeric_corruption','plan':key,'process':row['process']});report['checks']['numeric_corruption_refused_without_replay']=True
  service.execute=native;key=plan();result=apply(key,'terminal');d,_,_=service._load(key['planId'])
  with (d/'input_measure.txt').open('ab') as stream:stream.write(b' ')
  reject(lambda:apply(key,'terminal'),'target_changed');reject(lambda:service.recover(key['planId'],key['planDigest']),'target_changed');reject(lambda:service.inspect_measurements(key['planId'],key['planDigest']),'target_changed')
  report['cases'].append({'case':'terminal_measurement_tamper','plan':key,'result':result});report['checks']['terminal_tamper_read_apply_recover_refused']=True
  report['checks']['source_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
