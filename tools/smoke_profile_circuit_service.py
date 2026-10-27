import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.capture_pspice_netlist import CapturePSpiceNetlists
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_profile_circuits import PSpiceProfileCircuits
from cadence_mcp.pspice_cli_runs import PSpiceCliRuns
from cadence_mcp.pspice_dat import PSpiceDat

p=argparse.ArgumentParser(description='Native profile task lifecycle and solver acceptance over existing verified NET/ALS; no Capture GUI needed.')
for name in ('workspace-root','netlist-root','install-root','oracle','global-ini'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);old=a.netlist_root.resolve(strict=True)
net=json.loads((old/'report.json').read_text());assert net['passed'];source=root/'models-source';source.mkdir()
(source/'main.lib').write_text('* Own explicit nested library fixture\n.LIB "child.inc"\n.MODEL MCP_UNUSED D(IS=1e-14)\n',encoding='ascii')
(source/'child.inc').write_text('* Own transitive model fixture\n.MODEL MCP_UNUSED_CHILD D(IS=2e-14)\n',encoding='ascii')
before={str(x):sha256(x) for x in source.iterdir()};global_hash=sha256(a.global_ini)
cfg=Config(a.install_root,old/'work',(source,),30);inputs=PSpiceInputs(cfg)
def service(cls=PSpiceProfileCircuits):
 netlists=CapturePSpiceNetlists(cfg,CaptureService(cfg),GuiBridgeManager(()))
 return cls(cfg,netlists,inputs)
s=service();args=(net['plan']['planId'],net['plan']['planDigest'],[str(source/'main.lib')],True,
 ['.AC LIN 100 0.1 200','.OPTIONS ADVCONV','.PROBE64 V(alias(*)) I(alias(*)) W(alias(*)) D(alias(*)) NOISE(alias(*))'])
report={'passed':False,'publicProfileMcpAvailable':False,'fullV04Accepted':False,'fullP05Accepted':False}
try:
 cancelled=s.plan(*args);assert s.cancel(cancelled['planId'],cancelled['planDigest'])['state']=='cancelled';report['pendingCancelAccepted']=True
 plan=s.plan(*args);report['plan']=plan;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 result=s.apply(plan['planId'],plan['planDigest'],'native-profile-once');report['result']=result
 d=cfg.workspace_root/result['outputWorkspaceRelativePath'];hashes={str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}
 assert service().apply(plan['planId'],plan['planDigest'],'native-profile-once')==result
 assert {str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}==hashes;report['freshServiceIdempotence']=True
 opened=s.open_input(plan['planId'],plan['planDigest']);assert opened['fileCount']==5;report['prepared']=opened
 samples=json.loads(a.oracle.read_text(encoding='utf-8'))['cases']['after']
 cli=PSpiceCliRuns(cfg,inputs,PSpiceDat(cfg));cli_plan=cli.plan(opened['simulationId'],'ac',samples);cli_result=cli.apply(cli_plan['planId'],cli_plan['planDigest'],'profile-nested-model-cli')
 assert cli_result['numericalAcceptanceVerified'];report['solver']=cli_result;report['nestedModelClosureAndNumericsAccepted']=True
 class LoseVerificationObservation(PSpiceProfileCircuits):
  def verify(self,d,p,native_completed):
   result=super().verify(d,p,native_completed)
   if native_completed:raise CadenceError('native_completion_unknown','Injected observation loss after native profile verification.','verify')
   return result
 lost=service(LoseVerificationObservation);pending=lost.plan(*args);report['recoveryPlan']=pending
 try:lost.apply(pending['planId'],pending['planDigest'],'native-profile-observer-loss')
 except CadenceError as error:assert error.code=='native_completion_unknown'
 else:raise AssertionError('Expected injected observer loss')
 d=lost.root/('plan-'+pending['planId']);frozen={str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file() and x.name!='plan.json'}
 recovered=service().recover(pending['planId'],pending['planDigest']);assert recovered['mutationReplayed'] is False
 assert all(sha256(d/name)==value for name,value in frozen.items());report['freshServiceVerifyOnlyRecovery']=True
 report['passed']=True
except Exception as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
finally:
 report['modelsAndGlobalIniUnchanged']=all(sha256(Path(path))==digest for path,digest in before.items()) and sha256(a.global_ini)==global_hash
 report['passed']=report['passed'] and report['modelsAndGlobalIniUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','error','nestedModelClosureAndNumericsAccepted','freshServiceVerifyOnlyRecovery','modelsAndGlobalIniUnchanged')}))
if not report['passed']:raise SystemExit(1)
