"""Fixed native input-check interruption, missing proof and owned worker boundaries."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_input_checks import PSpiceInputChecks
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.environment import process_env
repo=Path(__file__).resolve().parents[1];root=repo/'.local/input-check-faults-v2-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();source=sources/'input.cir';source.write_bytes((repo/'.local/input-setup-probe-20261025/valid/input.cir').read_bytes());before=sha256(source)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(sources,),60);inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];checks=PSpiceInputChecks(cfg,inputs);native=checks.execute;verify=checks.verify
report={'passed':False,'cases':[],'checks':{}}
def plan(**kw):return checks.plan(sid,**kw)
def apply(key,label):return checks.apply(key['planId'],key['planDigest'],label)
def reject(action,code=None):
 try:action()
 except CadenceError as error:
  if code:assert error.code==code,(error.code,code)
  return error.code
 raise AssertionError('Unexpected acceptance')
def stopped(key):
 d,_,row=checks._load(key['planId']);p=row['process'];assert p['remainingOwnedProcesses']==0 and p['rootExitSignalConfirmed'] and p['observedProcessExitSignalsConfirmed'];return d,row
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
async def main():
 try:
  key=plan()
  def interrupt(d,p,native_completed):raise CadenceError('injected_validation_interrupt','Private validation interruption')
  checks.verify=interrupt;reject(lambda:apply(key,'interrupted'),'injected_validation_interrupt');d,row=stopped(key);assert row['process']['returnCode']==0
  hashes={n:sha256(d/n) for n in ('input.cir','result.out','receipt.json')};checks.verify=verify
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   args={k:key[k] for k in ('planId','planDigest')};r=await client.call_tool('pspice_recover_input_check',args);assert not r.is_error,r.structured_content;result=r.structured_content['data']
   assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and result['nativeReceiptVerified'] and result['nativeParserSetupVerified'] and not result['solverSuccessVerified'] and not result['mutationReplayed']
  assert hashes=={n:sha256(d/n) for n in hashes};report['cases'].append({'case':'validation_interrupted','plan':key,'process':row['process'],'recovered':result});report['checks']['fresh_receipt_backed_recovery_no_replay']=True
  key=plan()
  def lose(d,p,cancel,started):
   proc=native(d,p,cancel,started);assert proc['returnCode']==0;(d/'receipt.json').unlink();return proc
  checks.execute=lose;reject(lambda:apply(key,'lost'),'setup_completion_unverified');d,row=stopped(key)
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   r=await client.call_tool('pspice_recover_input_check',{k:key[k] for k in ('planId','planDigest')});assert r.is_error and r.structured_content['error']['code']=='setup_completion_unverified'
  reject(lambda:apply(key,'lost'),'write_not_replayed');report['cases'].append({'case':'missing_receipt','plan':key,'process':row['process']});report['checks']['error_free_out_without_native_receipt_not_certified']=True
  checks.execute=native;key=plan()
  def cancel_start(d,p,cancel,started):
   def ready(pid):started(pid);assert checks.cancel(key['planId'],key['planDigest'])['cancelRequested']
   return native(d,p,cancel,ready)
  checks.execute=cancel_start;reject(lambda:apply(key,'cancel'),'operation_cancelled');d,row=stopped(key);assert row['state']=='cancelled';report['cases'].append({'case':'active_cancel','plan':key,'process':row['process']});report['checks']['active_cancel_owned_zero']=True
  key=plan(timeout_seconds=1);delay=root/'delay.tcl';delay.write_text('after 3000\nexit 2\n',encoding='ascii')
  def timeout(d,p,cancel,started):return run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',delay],d,process_env(cfg),1,cancel=cancel,on_started=started)
  checks.execute=timeout;reject(lambda:apply(key,'timeout'),'timeout');d,row=stopped(key);report['cases'].append({'case':'timeout','plan':key,'process':row['process']});report['checks']['timeout_owned_zero']=True
  checks.execute=native;key=plan()
  def poison(d,p,cancel,started):
   proc=native(d,p,cancel,started);assert proc['returnCode']==0
   with (d/'input.cir').open('ab') as f:f.write(b'\n* changed job declaration\n')
   return proc
  checks.execute=poison;reject(lambda:apply(key,'poison'),'simulation_input_changed');d,row=stopped(key);reject(lambda:checks.recover(key['planId'],key['planDigest']),'simulation_input_changed');report['cases'].append({'case':'changed_job_input','plan':key});report['checks']['job_input_identity_refused']=True
  checks.execute=native;key=plan();result=apply(key,'terminal');d,_,_=checks._load(key['planId'])
  with (d/'result.out').open('ab') as f:f.write(b' ')
  reject(lambda:apply(key,'terminal'),'target_changed');reject(lambda:checks.recover(key['planId'],key['planDigest']),'target_changed');reject(lambda:checks.inspect(key['planId'],key['planDigest']),'target_changed');report['cases'].append({'case':'terminal_tamper','plan':key});report['checks']['terminal_inspect_apply_recover_hashes']=True
  key=plan();d,_,row=checks._load(key['planId']);frozen=Path(row['plan']['payload']['preparedDirectory'])/'input.cir';frozen.write_bytes(b'private frozen declaration corruption')
  reject(lambda:apply(key,'frozen'),'target_changed');_,_,row=checks._load(key['planId']);assert row['state']=='planned' and 'workerPid' not in row;report['cases'].append({'case':'frozen_prestart_tamper','plan':key});report['checks']['changed_frozen_input_never_started']=True
  report['checks']['source_unchanged']=sha256(source)==before;report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
