import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.capture_pspice_netlist import CapturePSpiceNetlists
from cadence_mcp.native_host_fence import read_fence

p=argparse.ArgumentParser(description='Real fixed native NET/ALS service acceptance; no public MCP availability claim.')
for key in ('workspace-root','source-root','binding','install-root','expected-netlist','expected-aliases'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_root.resolve(strict=True);binding=a.binding.resolve(strict=True)
cfg=Config(a.install_root,root/'work',(source,),30,gui_bridge_config=binding)
cap=CaptureService(cfg);ws=cap.create_workspace(str(source/'lowpassfilters.dsn'));sid=cap.open(ws['workspaceId'])['sessionId']
gui=GuiBridgeManager((binding,));found=gui.discover()['instances'];expected_pid=json.loads(binding.read_text())['expectedPid'];instance=next(x for x in found if x['pid']==expected_pid);gsid=gui.attach(instance['instanceId'],'read')['sessionId']
service=CapturePSpiceNetlists(cfg,cap,gui);report={'passed':False,'publicMcpAvailable':False}
try:
 plan=service.plan(sid,gsid,str(source/'LowPassFilters.opj'),str(source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim'));report['plan']=plan
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 result=service.apply(plan['planId'],plan['planDigest'],'native-service-once');report['result']=result;d=cfg.workspace_root/result['outputWorkspaceRelativePath']
 assert sha256(d/result['netlistRelativePath'])==sha256(a.expected_netlist)
 assert sha256(d/result['aliasesRelativePath'])==sha256(a.expected_aliases)
 assert read_fence(binding) is None
 before={str(p.relative_to(d)):sha256(p) for p in d.rglob('*') if p.is_file()}
 fresh=CapturePSpiceNetlists(cfg,CaptureService(cfg),GuiBridgeManager((binding,)))
 assert fresh.apply(plan['planId'],plan['planDigest'],'native-service-once')==result
 assert {str(p.relative_to(d)):sha256(p) for p in d.rglob('*') if p.is_file()}==before
 report.update(freshServiceIdempotence=True,fenceReleased=True,netAndAliasesMatchIndependentOracle=True)
 args=(sid,gsid,str(source/'LowPassFilters.opj'),str(source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim'))
 pending=service.plan(*args);cancelled=service.cancel(pending['planId'],pending['planDigest'])
 pending_dir=service.root/('plan-'+pending['planId'])
 assert cancelled['state']=='cancelled' and {x.name for x in pending_dir.iterdir()}=={'plan.json'}
 report['cancelBeforeDispatchAccepted']=True
 class LoseCompletionObservation(CapturePSpiceNetlists):
  def _wait_completion(self,d,p):
   super()._wait_completion(d,p)
   raise CadenceError('native_completion_unknown','Injected observer loss after real native completion; no replay.','worker')
 lost=LoseCompletionObservation(cfg,cap,gui);recovery_plan=lost.plan(*args)
 report['recoveryPlan']=recovery_plan
 try:lost.apply(recovery_plan['planId'],recovery_plan['planDigest'],'native-observer-loss')
 except CadenceError as error:assert error.code=='native_completion_unknown'
 else:raise AssertionError('Injected observation loss did not fail apply')
 owner=read_fence(binding);assert owner and owner['jobId']==recovery_plan['planId']
 report['observerLossRetainedFence']=True
 try:service.plan(*args)
 except CadenceError as error:assert error.code=='bridge_busy'
 else:raise AssertionError('Unresolved host allowed new native dispatch')
 report['pendingFenceBlocksNewPlan']=True
 recovery_dir=lost.root/('plan-'+recovery_plan['planId'])
 preserved={str(x.relative_to(recovery_dir)):sha256(x) for x in recovery_dir.rglob('*') if x.is_file() and x.name!='plan.json'}
 fresh=CapturePSpiceNetlists(cfg,CaptureService(cfg),GuiBridgeManager((binding,)))
 recovered=fresh.recover(recovery_plan['planId'],recovery_plan['planDigest'])
 assert recovered['mutationReplayed'] is False and recovered['nativeCompletionVerified'] and read_fence(binding) is None
 assert all(sha256(recovery_dir/name)==value for name,value in preserved.items())
 assert sha256(recovery_dir/recovered['netlistRelativePath'])==sha256(a.expected_netlist)
 assert sha256(recovery_dir/recovered['aliasesRelativePath'])==sha256(a.expected_aliases)
 verified={str(x.relative_to(recovery_dir)):sha256(x) for x in recovery_dir.rglob('*') if x.is_file()}
 repeated=fresh.recover(recovery_plan['planId'],recovery_plan['planDigest'])
 assert repeated['nativeCompletionVerified']
 assert {str(x.relative_to(recovery_dir)):sha256(x) for x in recovery_dir.rglob('*') if x.is_file()}==verified
 report.update(recoveryWithoutNativeReplay=True,recoveryReleasedFence=True,repeatedRecoveryFilesUnchanged=True,passed=True)
except Exception as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
finally:
 cap.close(sid)
 try:gui.detach(gsid)
 except Exception as error:report['detachObservation']=str(error)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:report.get(k) for k in ['passed','error','fenceReleased','freshServiceIdempotence']}))
if not report['passed']:raise SystemExit(1)
