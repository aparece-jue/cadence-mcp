"""Private native menu DRC probe; native execution may save the supplied private DSN/OPJ."""
import argparse,json,subprocess,time
from pathlib import Path
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.core import sha256
p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=json.loads(a.binding.read_text(encoding='utf-8'));source=Path(cfg['expectedDesign']);assert '.local' in source.parts and source.stem=='MCP_DRC_ERROR';hello=RpcConnection(a.binding).call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean';exe=Path(cfg['expectedExecutable']);assert process_image(cfg['expectedPid'])==exe;before=sha256(source);expected=json.loads((source.parent/'expected.json').read_text(encoding='utf-8'));assert before==expected['sourceSha256'];prior={x.name:{'sha256':sha256(x),'mtimeNs':x.stat().st_mtime_ns} for x in source.parent.iterdir() if x.is_file()};output=root/'native-result.json';code=r'''
if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]] || [::cmcpBridge::dirty] ne "clean"} {error wrong_or_dirty_design}
package require OrEntryDRCConfig
namespace eval ::cmcpDrcMenuProbe {
 set callbackCount 0
 set originalConfig [capGetDRCConfigData]
 set parsed [::json::json2dict $originalConfig]
 if {![string equal -nocase [file normalize [dict get $parsed DesignPath]] [file normalize DESIGN]] || [dict get $parsed RunElectricalRules] ne "1" || [dict exists $parsed DoModal]} {error unexpected_original_configuration}
 set reportPath [file normalize [dict get $parsed ReportFileName]]
 if {![string equal -nocase [file dirname $reportPath] [file dirname [file normalize DESIGN]]] || [file exists $reportPath]} {error unsafe_or_preexisting_report}
 set stream [open ORIGINAL {WRONLY CREAT EXCL}];puts $stream $originalConfig;close $stream
 set runConfig "\{\"DoModal\":\"1\",[string range $originalConfig 1 end]"
 if {[dict get [::json::json2dict $runConfig] DoModal] ne "1"} {error invalid_run_configuration}
 if {![llength [info procs ::OrHandlerDRCConfig::capDRCConfigLaunchWidget]] || [llength [info commands ::cmcpDrcMenuProbe::originalLaunch]]} {error callback_unavailable}
 set originalBody [info body ::OrHandlerDRCConfig::capDRCConfigLaunchWidget]
 rename ::OrHandlerDRCConfig::capDRCConfigLaunchWidget ::cmcpDrcMenuProbe::originalLaunch
 proc ::OrHandlerDRCConfig::capDRCConfigLaunchWidget {} {
  incr ::cmcpDrcMenuProbe::callbackCount
  set f [open CALLED {WRONLY CREAT EXCL}];puts $f [pid];close $f
  return $::cmcpDrcMenuProbe::runConfig
 }
 set f [open STARTED {WRONLY CREAT EXCL}];puts $f [pid];close $f
 set rc [catch {
  try {SelectPMItem "./MCP_DRC_ERROR.dsn";set menuResult [Menu "PCB::Design Rules Check"]} finally {
   rename ::OrHandlerDRCConfig::capDRCConfigLaunchWidget {}
   rename ::cmcpDrcMenuProbe::originalLaunch ::OrHandlerDRCConfig::capDRCConfigLaunchWidget
  }
 } message]
 set restored [expr {[string equal [info body ::OrHandlerDRCConfig::capDRCConfigLaunchWidget] $originalBody]}]
 set afterConfig [capGetDRCConfigData]
 set f [open AFTER {WRONLY CREAT EXCL}];puts $f $afterConfig;close $f
 set f [open OUTPUT {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj pid [pid] invocationReturned [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]] callbackCount $callbackCount callbackRestored [expr {$restored?"true":"false"}] menuResult [cmcp::q [expr {[info exists menuResult]?$menuResult:""}]] dirtyAfter [cmcp::q [::cmcpBridge::dirty]]]} finally {close $f}
}
'''
for k,v in {'PID':str(cfg['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'ORIGINAL':tcl_string((root/'original-config.json').as_posix()),'AFTER':tcl_string((root/'after-config.json').as_posix()),'CALLED':tcl_string((root/'callback-called.txt').as_posix()),'STARTED':tcl_string((root/'started.txt').as_posix()),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace(k,v)
payload=root/'probe.tcl';payload.write_text(code,encoding='utf-8');(root/'check-complete.tcl').write_text('set f [open [lindex $argv 0]]\nset code [read $f]\nclose $f\nputs [info complete $code]\nif {![info complete $code]} {exit 1}\n',encoding='utf-8');syntax=subprocess.run([str(exe.parents[2]/'tcltk/bin/tclsh.exe'),str(root/'check-complete.tcl'),str(payload)],capture_output=True,text=True);assert syntax.returncode==0 and syntax.stdout.strip()=='1', 'Tcl completeness refused';wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;started=time.time_ns();child=subprocess.Popen([str(exe),str(wrapper)],startupinfo=startup);end=time.monotonic()+25
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'accepted':False,'sourceBefore':before,'startedUnixNs':started,'sourceDirectoryBefore':prior,'acknowledged':output.exists(),'launcherPid':child.pid,'noReplay':True}
if child.poll() is None:assert child.pid!=cfg['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
if output.exists():report['native']=json.loads(output.read_text(encoding='utf-8'))
if (root/'after-config.json').exists():report['configurationUnchanged']=json.loads((root/'original-config.json').read_text(encoding='utf-8'))==json.loads((root/'after-config.json').read_text(encoding='utf-8'))
report['sourceUnchanged']=sha256(source)==before;report['sourceDirectoryAfter']={x.name:{'sha256':sha256(x),'mtimeNs':x.stat().st_mtime_ns,'fresh':x.stat().st_mtime_ns>=started} for x in source.parent.iterdir() if x.is_file()};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('sourceDirectoryBefore','sourceDirectoryAfter')}),flush=True)
