"""One authenticated local online-DRC diagnostic on a private Capture design; no save/replay."""
import argparse,json,subprocess,time,shutil
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS
p=argparse.ArgumentParser()
for n in ('binding','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=json.loads(a.binding.read_text(encoding='utf-8'));hello=RpcConnection(a.binding).call('hello',{});assert not hello['data']['bindingLost'];exe=Path(cfg['expectedExecutable']);assert process_image(cfg['expectedPid'])==exe;source=Path(cfg['expectedDesign']);assert '.local' in source.parts and '.local' in root.parts;before=sha256(source);project=source.with_suffix('.opj');project_hash=sha256(project);output=root/'native-result.json'
logs=[p for p in source.parent.iterdir() if p.name.lower()==source.stem.lower()+'_drc.log'];assert len(logs)<=1;prior_log={'exists':bool(logs)}
if logs:prior_log.update(sha256=sha256(logs[0]),mtimeNs=logs[0].stat().st_mtime_ns)
started_ns=time.time_ns()
code=r'''if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]]} {error wrong_design}
namespace eval ::cmcpHostDrcProbe {
 set design [GetActivePMDesign];if {$design eq "NULL"} {error no_design}
 set f [open BOOT {WRONLY CREAT EXCL}];puts $f [pid];close $f
 set originalConfig [capGetDRCConfigData]
 if {![regexp {"RunElectricRuleWiresOnline"\s*:\s*"([01])"} $originalConfig -> priorFlag] || $priorFlag!=0} {error unexpected_original_rule}
 set f [open ORIGINAL {WRONLY CREAT EXCL}];puts $f $originalConfig;close $f
 set runResult "";set dumpResult "";set enableResult "";set duringConfig "";set restoreResult "";set countsAfter {};set rc [catch {
  try {
   set enableResult [::COrDRCTclInterface_EnableDRC $design "DRC_Check_Unconnected_Nets_Online" true]
   set duringConfig [capGetDRCConfigData]
   if {![regexp {"RunElectricRuleWiresOnline"\s*:\s*"1"} $duringConfig]} {error rule_not_observably_enabled}
   set runResult [::COrDRCTclInterface_CleanAndRunOnlineDRC $design]
   set designName [DboTclHelper_sMakeStdStr [::cmcpBridge::nameOf $design]]
   foreach severity {DRC_ERROR DRC_WARNING} {set constant ::COrDRCTclInterface_$severity;lappend countsAfter [cmcp::obj severity [cmcp::q $severity] count [::COrDRCTclInterface_GetElectricalDRCCount $designName [set $constant]]]}
   set dumpResult [::COrDRCTclInterface_DumpAllDRCErrorToLogFile $design]
  } finally {set restoreResult [::COrDRCTclInterface_EnableDRC $design "DRC_Check_Unconnected_Nets_Online" false]}
 } message]
 set restoredConfig [capGetDRCConfigData]
 set f [open OUTPUT {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj pid [pid] invocationReturned [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]] runResult [cmcp::q [expr {[info exists runResult]?$runResult:""}]] dumpResult [cmcp::q [expr {[info exists dumpResult]?$dumpResult:""}]] enableResult [cmcp::q $enableResult] restoreResult [cmcp::q $restoreResult] countsAfter [cmcp::arr $countsAfter] originalConfig [cmcp::q $originalConfig] duringConfig [cmcp::q $duringConfig] restoredConfig [cmcp::q $restoredConfig]]} finally {close $f}
}
'''
for k,v in {'PID':str(cfg['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'BOOT':tcl_string((root/'entered.txt').as_posix()),'ORIGINAL':tcl_string((root/'original-config.json').as_posix()),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace(k,v)
payload=root/'probe.tcl';payload.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=startup);end=time.monotonic()+30
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'scope':'local online DRC invocation only; not full report/clean-error acceptance','expectedPid':cfg['expectedPid'],'launcherPid':child.pid,'acknowledged':output.exists(),'sourceSha256':before,'noReplay':True}
if child.poll() is None:assert child.pid!=cfg['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
if output.exists():report['receipt']=json.loads(output.read_text(encoding='utf-8'))
report['priorNativeLog']=prior_log;report['startedUnixNs']=started_ns
logs=[p for p in source.parent.iterdir() if p.name.lower()==source.stem.lower()+'_drc.log']
if len(logs)==1:
 log=logs[0];report['nativeLog']={'sha256':sha256(log),'mtimeNs':log.stat().st_mtime_ns,'fresh':log.stat().st_mtime_ns>=started_ns,'sourceRelativeName':log.name};shutil.copy2(log,root/'native-report.log')
report['projectUnchanged']=sha256(project)==project_hash
if output.exists():
 receipt=report['receipt'];report['configurationRestored']=json.loads(receipt['originalConfig'])==json.loads(receipt['restoredConfig']);report['onlineRuleObservedEnabled']=json.loads(receipt['duringConfig']).get('RunElectricRuleWiresOnline')=='1' if receipt['duringConfig'] else False
report['sourceUnchanged']=sha256(source)==before;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='receipt'},ensure_ascii=True),flush=True)
