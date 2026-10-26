"""Private fixed Capture command introspection after authenticated recovery; no business operation."""
import argparse,json,subprocess,time
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS
p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);config=json.loads(a.binding.read_text(encoding='utf-8'));hello=RpcConnection(a.binding).call('hello',{});assert not hello['data']['bindingLost'];exe=Path(config['expectedExecutable']);assert process_image(config['expectedPid'])==exe;source=Path(config['expectedDesign']);before=sha256(source);output=root/'commands.json'
code='''if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]]} {error wrong_design}
namespace eval ::cmcpHostCommandProbe {
set rows {}
foreach name [lsort -unique [concat [info commands ::*DRC*] [info commands ::*Drc*] [list ::new_CorSimSrvr ::CorSimSrvr_loadProfile ::CorSimSrvr_loadDesign ::CorSimSrvr_getRunStatus ::CorSimSrvr_readSettingsLibinc ::CorSimSrvr_setProjectPathForLibinc ::CorSimSrvr_unloadDesign]]] {
 set exists [expr {[llength [info commands $name]]>0}];set argsList {};set body "";set signature ""
 if {$exists} {
  if {[llength [info procs $name]]} {foreach arg [info args $name] {lappend argsList [cmcp::q $arg]};set body [string range [info body $name] 0 32767]} else {catch {$name {*}[lrepeat 100 __CMCP_INVALID_TYPE__]} signature;set signature [string range $signature 0 4095]}
 }
 lappend rows [cmcp::obj name [cmcp::q $name] exists $exists procedureArgs [cmcp::arr $argsList] body [cmcp::q $body] signatureRefusal [cmcp::q $signature]]
}
set f [open OUTPUT {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj pid [pid] commands [cmcp::arr $rows] businessOperationExecuted false]} finally {close $f}
}
'''
for k,v in {'PID':str(config['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace(k,v)
payload=root/'probe.tcl';payload.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=startup);end=time.monotonic()+20
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'confirmed':output.exists(),'expectedPid':config['expectedPid'],'launcherPid':child.pid,'sourceUnchanged':sha256(source)==before}
if child.poll() is None:assert child.pid!=config['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
