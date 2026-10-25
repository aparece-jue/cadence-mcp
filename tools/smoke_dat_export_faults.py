"""Native DAT export fault acceptance; only owned copies and fixed workers."""
import argparse, asyncio, json, os, sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config, CadenceError, sha256
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_exports import PSpiceExports
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.environment import process_env

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source-dat'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=a.source_dat.resolve(strict=True);before=sha256(source)
cfg=Config(a.install_root.resolve(strict=True),root/'work',(source.parent,),60)
data=PSpiceDat(cfg);ident=data.open(str(source))['datId'];exports=PSpiceExports(cfg,data)
native=exports.execute;report={'passed':False,'checks':{},'cases':[],'sourceBefore':before}
def plan():return exports.plan(ident,0,'Gain','csv',0,3)
def apply(service,key,label):return service.apply(key['planId'],key['planDigest'],label)
def rejected(action,expected=None):
 try:action()
 except CadenceError as error:
  if expected is not None:assert error.code==expected,(error.code,expected)
  return error.code
 raise AssertionError('Operation unexpectedly accepted')
def stopped(service,key):
 d,_,row=service._load(key['planId']);proc=row['process']
 assert proc['remainingOwnedProcesses']==0 and proc['rootExitSignalConfirmed'] and proc['observedProcessExitSignalsConfirmed'],proc
 return d,row
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)

async def main():
 try:
  # Successful serializer bytes survive lost receipt; fresh server only verifies.
  key=plan();calls=[]
  def lose(d,p,cancel,started):
   calls.append(str(d));proc=native(d,p,cancel,started)
   assert proc['returnCode']==0
   (d/'receipt.json').unlink();return proc
  exports.execute=lose;code=rejected(lambda:apply(exports,key,'lost'))
  d,row=stopped(exports,key);assert row['state']=='failed'
  hashes={n:sha256(d/n) for n in ('source.dat','samples.csv')}
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   assert len((await fresh.list_tools()).tools)==160
   r=await fresh.call_tool('pspice_recover_dat_export',{k:key[k] for k in ('planId','planDigest')})
   assert not r.is_error,r.structured_content
   result=r.structured_content['data'];assert result['state']=='verified_recovered' and not result['workerCompletionVerified'] and result['nativeReopenVerified'] and not result['mutationReplayed']
   again=await fresh.call_tool('pspice_apply_dat_export',{**{k:key[k] for k in ('planId','planDigest')},'idempotencyKey':'lost'})
   assert not again.is_error and not again.structured_content['data']['mutationReplayed']
  assert len(calls)==1 and hashes=={n:sha256(d/n) for n in hashes}
  report['cases'].append({'case':'lost_receipt','plan':key,'error':code,'process':row['process'],'recovered':result})
  report['checks']['fresh_recovery_without_numeric_regeneration']=True
  print('receipt recovery passed',flush=True)
  # Cancel before the suspended serializer is resumed.
  exports.execute=native;key=plan()
  def cancel_start(d,p,cancel,started):
   def ready(pid):
    started(pid);assert exports.cancel(key['planId'],key['planDigest'])['cancelRequested']
   return native(d,p,cancel,ready)
  exports.execute=cancel_start
  rejected(lambda:apply(exports,key,'cancel'),'operation_cancelled')
  d,row=stopped(exports,key);assert row['state']=='cancelled' and not (d/'samples.csv').exists()
  report['cases'].append({'case':'active_cancel','plan':key,'process':row['process']})
  report['checks']['active_cancel_owned_tree_stopped']=True
  # Timeout uses a private fixed delay in front of the production serializer.
  short=Config(cfg.install_root,cfg.workspace_root,cfg.read_roots,1)
  timed=PSpiceExports(short,data);key=timed.plan(ident,0,'Gain','csv',0,3)
  delay=root/'delay.py';delay.write_text('import time\ntime.sleep(3)\nfrom cadence_mcp.pspice_export_worker import main\nraise SystemExit(main())\n',encoding='utf-8')
  def timeout(d,p,cancel,started):
   cmd=timed.native_command(d,p)
   return run_owned_process([cmd[0],str(delay),*cmd[3:]],d,process_env(short),1,cancel=cancel,on_started=started)
  timed.execute=timeout;rejected(lambda:apply(timed,key,'timeout'),'timeout')
  d,row=stopped(timed,key);assert not (d/'samples.csv').exists()
  report['cases'].append({'case':'timeout','plan':key,'process':row['process']})
  report['checks']['timeout_owned_tree_stopped']=True
  # Corrupted numeric output must fail independent native reread and recovery.
  exports.execute=native;key=plan()
  def poison(d,p,cancel,started):
   proc=native(d,p,cancel,started);assert proc['returnCode']==0
   with (d/'samples.csv').open('ab') as stream:stream.write(b'0,0,0,999,0\n')
   return proc
  exports.execute=poison;rejected(lambda:apply(exports,key,'poison'),'export_mismatch')
  d,row=stopped(exports,key);assert row['state']=='failed'
  rejected(lambda:exports.recover(key['planId'],key['planDigest']),'export_mismatch')
  rejected(lambda:apply(exports,key,'poison'),'write_not_replayed')
  report['cases'].append({'case':'numeric_corruption','plan':key,'process':row['process']})
  report['checks']['corrupt_numeric_bytes_not_recovered_or_replayed']=True
  # Each accepted artifact member is covered by terminal reuse/recovery hashes.
  exports.execute=native
  for name in ('source.dat','samples.csv','export-manifest.json'):
   key=plan();result=apply(exports,key,'terminal-'+name);d,_,_=exports._load(key['planId'])
   with (d/name).open('ab') as stream:stream.write(b' ')
   rejected(lambda:apply(exports,key,'terminal-'+name),'target_changed')
   rejected(lambda:exports.recover(key['planId'],key['planDigest']),'target_changed')
   report['cases'].append({'case':'terminal_tamper','file':name,'plan':key,'before':result['files']})
  report['checks']['all_three_terminal_file_hashes_enforced']=True
  data.close(ident);report['checks']['original_source_unchanged']=sha256(source)==before
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['sourceAfter']=sha256(source)
  if report['sourceAfter']!=before:report['passed']=False
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
