"""One fixed local PSpice NET call in an authenticated private Capture host; never retry a dispatch."""
import argparse,json,subprocess,time
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS
p=argparse.ArgumentParser()
for n in ('binding','workspace-root','install-root'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument("--oracle",type=Path)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);binding=json.loads(a.binding.read_text(encoding='utf-8'));hello=RpcConnection(a.binding).call('hello',{});assert not hello['data']['bindingLost'];exe=Path(binding['expectedExecutable']);assert process_image(binding['expectedPid'])==exe;source=Path(binding['expectedDesign']);assert '.local' in source.parts and '.local' in root.parts;before=sha256(source)
oracle_hash=None
if a.oracle:
 oracle_data=json.loads(a.oracle.read_text(encoding='utf-8'));assert oracle_data['sourceFingerprint']==before;oracle_hash=sha256(a.oracle)
target=root/'generated.net';output=root/'native-result.json';boot=root/'entered.txt';assert not target.exists()
code='''if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]]} {error wrong_design}
namespace eval ::cmcpHostNetlistProbe {
 set design DESIGN;set target TARGET;set output OUTPUT
 if {[file exists $target]} {error output_exists}
 set f [open BOOT {WRONLY CREAT EXCL}];puts $f [pid];close $f
 set result "";set phase load
 set rc [catch {
  if {![llength [info commands ::OrTclNetlist_sCreatePSpiceNetList]]} {load DLL orTclNetlist}
  set phase generate
  set result [::OrTclNetlist_sCreatePSpiceNetList $design $target false false false false true true ""]
  set phase returned
 } message]
 set logs {}
 foreach {name command} {errors ::OrTclNetlist_sGetErrorLog warnings ::OrTclNetlist_sGetWarningLog session ::OrTclNetlist_sGetSessionLog netlist ::OrTclNetlist_sGetNetlistLog} {
  set values {};set vec [DboTclHelper_sMakeStdVector];set status [catch {$command $vec} logError]
  if {!$status} {set size [DboTclHelper_sGetVectorSize $vec];if {$size>10000} {error log_limit};for {set i 0} {$i<$size} {incr i} {lappend values [cmcp::q [string range [DboTclHelper_sGetConstCharPtrFromVector $vec $i] 0 2047]]}}
  lappend logs [cmcp::obj category [cmcp::q $name] readable [expr {$status?"false":"true"}] lines [cmcp::arr $values]]
 }
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj pid [pid] invocationReturned [expr {$rc?"false":"true"}] phase [cmcp::q $phase] nativeReturn [cmcp::q $result] error [cmcp::q [expr {$rc?$message:""}]] logs [cmcp::arr $logs]]} finally {close $f}
}
'''
for k,v in {'PID':str(binding['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'TARGET':tcl_string(target.as_posix()),'OUTPUT':tcl_string(output.as_posix()),'BOOT':tcl_string(boot.as_posix()),'DLL':tcl_string((a.install_root/'tools/bin/orTclNetlist64.dll').as_posix())}.items():code=code.replace(k,v)
payload=root/'probe.tcl';payload.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=startup);end=time.monotonic()+30
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'scope':'fixed local OrTclNetlist call, not remote ASP wrapper','sourceSha256':before,'expectedPid':binding['expectedPid'],'launcherPid':child.pid,'acknowledged':output.exists(),'entered':boot.exists(),'targetAbsentBefore':True,'noReplay':True,'oracleSha256':oracle_hash}
if child.poll() is None:assert child.pid!=binding['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
if output.exists():report['receipt']=json.loads(output.read_text(encoding='utf-8'))
report['targetSize']=target.stat().st_size if target.exists() else None
if target.exists():report['targetSha256']=sha256(target)
report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=not a.oracle or sha256(a.oracle)==oracle_hash;report['nonemptyNetProduced']=bool(report['acknowledged'] and report['targetSize']);(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'acknowledged':report['acknowledged'],'entered':report['entered'],'targetSize':report['targetSize'],'sourceUnchanged':report['sourceUnchanged'],'receipt':report.get('receipt')},ensure_ascii=True),flush=True)
