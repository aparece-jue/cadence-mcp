"""Developer fault injection after real native DLL loading; never changes a source design."""
import argparse,json,threading,time
from pathlib import Path
from unittest.mock import patch
import cadence_mcp.pspice_profile_circuits as module
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.capture_pspice_netlist import CapturePSpiceNetlists
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.gui_loader import tcl_string

p=argparse.ArgumentParser()
for name in ('workspace-root','netlist-root','library','install-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);old=a.netlist_root.resolve(strict=True);net=json.loads((old/'report.json').read_text());assert net['passed'];library=a.library.resolve(strict=True)
cfg=Config(a.install_root,old/'work',(library.parent,),30);netlists=CapturePSpiceNetlists(cfg,CaptureService(cfg),GuiBridgeManager(()));s=module.PSpiceProfileCircuits(cfg,netlists,PSpiceInputs(cfg));report={'passed':False,'scope':'Owned profile-worker cancellation and timeout after native DLL load, not cancellation inside updateCirFileI','cases':{}}
original_run=module.run_owned_process;source_hashes={str(x):sha256(x) for x in library.parent.rglob('*') if x.is_file()}
try:
 for mode in ('cancel','timeout'):
  plan=s.plan(net['plan']['planId'],net['plan']['planDigest'],[str(library)],True,['.AC LIN 100 0.1 200']);d=s.root/('plan-'+plan['planId']);marker=d/'dlls-loaded.txt';cancel_result={}
  def injected(argv,cwd,env,timeout_seconds,cancel=None,on_started=None):
   code='foreach {dll init} {orPSpiceExplorer64.dll orPSpiceExplorer orCommonTcl64.dll orCommonTcl orSimSrvr64.dll orSimSrvr} {load [file join '+tcl_string(cfg.install_root.as_posix())+' tools bin $dll] $init}\n'
   code+='set f [open '+tcl_string(marker.as_posix())+' {WRONLY CREAT EXCL}];puts $f [pid];close $f\nafter 60000\n'
   Path(argv[1]).write_text(code,encoding='utf-8')
   return original_run(argv,cwd,env,3,cancel=cancel,on_started=on_started)
  def request_cancel():
   until=time.monotonic()+5
   while not marker.exists() and time.monotonic()<until:time.sleep(.02)
   if marker.exists():cancel_result.update(s.cancel(plan['planId'],plan['planDigest']))
  thread=threading.Thread(target=request_cancel) if mode=='cancel' else None
  if thread:thread.start()
  with patch.object(module,'run_owned_process',injected):
   try:s.apply(plan['planId'],plan['planDigest'],'profile-loaded-dll-'+mode)
   except CadenceError as error:assert error.code==('operation_cancelled' if mode=='cancel' else 'timeout'),error.code
   else:raise AssertionError('Faulted profile worker reported success')
  if thread:thread.join(timeout=6);assert not thread.is_alive() and cancel_result.get('cancelRequested') is True
  row=json.loads((d/'plan.json').read_text());process=row['process']
  assert marker.exists() and int(marker.read_text())==row['workerPid']==process['pid']
  assert process['state']==('cancelled' if mode=='cancel' else 'timeout') and process['remainingOwnedProcesses']==0
  assert process['rootExitSignalConfirmed'] and process['observedProcessExitSignalsConfirmed']
  assert not (d/'native-result.json').exists() and not (d/'circuit-artifacts.json').exists()
  frozen={str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}
  try:s.recover(plan['planId'],plan['planDigest'])
  except CadenceError:pass
  else:raise AssertionError('Missing completion receipt was accepted by recover')
  assert {str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}==frozen
  report['cases'][mode]={'plan':plan,'process':process,'dllLoadMarkerVerified':True,'noCompletionReceiptAccepted':True,'recoverDidNotReplay':True}
 report['modelSourcesUnchanged']=all(sha256(Path(path))==digest for path,digest in source_hashes.items());assert report['modelSourcesUnchanged'];report['passed']=True
except Exception as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
finally:
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','error','modelSourcesUnchanged')}))
if not report['passed']:raise SystemExit(1)
