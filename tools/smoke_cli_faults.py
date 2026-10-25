"""Official CLI owned-process and artifact failure acceptance."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_cli_runs import PSpiceCliRuns
repo=Path(__file__).resolve().parents[1];root=repo/'.local/cli-faults-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();source=sources/'divider.cir';source.write_bytes((repo/'.local/pspice-owned-7797dd67a5/source/divider.cir').read_bytes());before=sha256(source)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(sources,),60);inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];cli=PSpiceCliRuns(cfg,inputs,PSpiceDat(cfg));native=cli.execute
expected={'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
report={'passed':False,'checks':{},'cases':[]}
def plan(points=None,timeout=None):return cli.plan(sid,'dc',[expected] if points is None else points,timeout)
def apply(key,label):return cli.apply(key['planId'],key['planDigest'],label)
def reject(action,code=None):
 try:action()
 except CadenceError as error:
  if code:assert error.code==code,(error.code,code)
  return error.code
 raise AssertionError('Unexpected acceptance')
def stopped(key):
 d,_,row=cli._load(key['planId']);p=row['process'];assert p['remainingOwnedProcesses']==0 and p['rootExitSignalConfirmed'] and p['observedProcessExitSignalsConfirmed'];return d,row
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
async def main():
 try:
  key=plan();calls=[]
  def lose(d,p,cancel,started):
   calls.append(d);proc=native(d,p,cancel,started);assert proc['returnCode']==0;(d/'cli-receipt.json').unlink();return proc
  cli.execute=lose;error=reject(lambda:apply(key,'lost'));d,row=stopped(key);hashes={n:sha256(d/n) for n in ('input.out','input.dat','result.out','result.dat')}
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   args={k:key[k] for k in ('planId','planDigest')};r=await client.call_tool('pspice_recover_cli_run',args);assert not r.is_error,r.structured_content;result=r.structured_content['data']
   assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and result['numericalAcceptanceVerified'] and not result['mutationReplayed']
   r=await client.call_tool('pspice_apply_cli_run',{**args,'idempotencyKey':'lost'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
  assert len(calls)==1 and hashes=={n:sha256(d/n) for n in hashes};report['cases'].append({'case':'lost_receipt','plan':key,'error':error,'process':row['process'],'recovered':result});report['checks']['fresh_receipt_loss_recovery_no_replay']=True
  cli.execute=native;key=plan()
  def cancel_start(d,p,cancel,started):
   def ready(pid):started(pid);assert cli.cancel(key['planId'],key['planDigest'])['cancelRequested']
   return native(d,p,cancel,ready)
  cli.execute=cancel_start;reject(lambda:apply(key,'cancel'),'operation_cancelled');d,row=stopped(key);assert row['state']=='cancelled';report['cases'].append({'case':'active_cancel','plan':key,'process':row['process']});report['checks']['active_cli_cancel_owned_zero']=True
  cli.execute=native;key=plan(timeout=1);reject(lambda:apply(key,'timeout'),'timeout');d,row=stopped(key);report['cases'].append({'case':'actual_cli_timeout','plan':key,'process':row['process']});report['checks']['actual_cli_timeout_owned_zero']=True
  key=plan()
  def corrupt_raw(d,p,cancel,started):
   proc=native(d,p,cancel,started);assert proc['returnCode']==0
   with (d/'input.dat').open('ab') as f:f.write(b'corrupt raw')
   return proc
  cli.execute=corrupt_raw;reject(lambda:apply(key,'raw'),'target_changed');d,row=stopped(key);reject(lambda:cli.recover(key['planId'],key['planDigest']),'target_changed');report['cases'].append({'case':'raw_data_corrupt','plan':key});report['checks']['raw_native_identity_mismatch_refused']=True
  cli.execute=native;key=plan();result=apply(key,'terminal');d,_,_=cli._load(key['planId'])
  with (d/'result.dat').open('ab') as f:f.write(b'changed canonical')
  reject(lambda:apply(key,'terminal'),'target_changed');reject(lambda:cli.recover(key['planId'],key['planDigest']),'target_changed');reject(lambda:cli.open_dat(key['planId'],key['planDigest']),'target_changed');report['cases'].append({'case':'terminal_canonical_corrupt','plan':key});report['checks']['terminal_hashes_and_open_refuse']=True
  key=plan([{**expected,'real':3.0}]);reject(lambda:apply(key,'wrong'),'simulation_expectation_mismatch');d,row=stopped(key);reject(lambda:cli.recover(key['planId'],key['planDigest']),'simulation_expectation_mismatch');report['cases'].append({'case':'wrong_numeric_oracle','plan':key});report['checks']['wrong_independent_oracle_refused']=True
  key=plan();d,_,_=cli._load(key['planId']);old=d/'input.out';old.write_bytes(b'OLD PRIVATE OUTPUT')
  reject(lambda:apply(key,'old'),'preexisting_cli_output');_,_,row=cli._load(key['planId']);assert row['workerPid'] is None and 'process' not in row and old.read_bytes()==b'OLD PRIVATE OUTPUT';reject(lambda:apply(key,'old'),'write_not_replayed');report['cases'].append({'case':'old_output_before_start','plan':key});report['checks']['old_output_not_started_overwritten_or_replayed']=True
  key=plan();_,_,row=cli._load(key['planId']);(Path(row['plan']['payload']['preparedDirectory'])/'input.cir').write_bytes(b'changed frozen input')
  reject(lambda:apply(key,'frozen'),'target_changed');_,_,row=cli._load(key['planId']);assert row['state']=='planned' and 'workerPid' not in row;report['cases'].append({'case':'changed_frozen_input','plan':key});report['checks']['frozen_change_prestart_rejected']=True
  report['checks']['source_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle;report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
