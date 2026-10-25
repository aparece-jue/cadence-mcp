"""Trusted inventory forwarded to an already observed Capture PID; no design action."""
import argparse,json,subprocess,time
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.bridge_rpc import process_image
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--pid',type=int,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);exe=(a.install_root/'tools/bin/Capture.exe').resolve(strict=True);assert process_image(a.pid)==exe
output=root/'runtime.json';payload=root/'inventory.tcl';wrapper=root/'invoke.tcl'
code='''# PID-bound inventory, no retarget, design open, native mutation or exit.
if {[pid]!=PID} {error wrong_capture_process}
source JSONHELPER
set ::cmcpInventoryRows {}
foreach ::cmcpInventoryCommand [lsort -unique [concat [info commands *PSpice*] [info commands *pspice*] [info commands *Netlist*] [info commands *NetList*] [info commands *DRC*] [info commands *Open*]]] {
 lappend ::cmcpInventoryRows [cmcp::q $::cmcpInventoryCommand]
}
set ::cmcpInventoryF [open OUTPUT {WRONLY CREAT EXCL}]
puts $::cmcpInventoryF [cmcp::obj pid [pid] commands [cmcp::arr $::cmcpInventoryRows] designOpenedByProbe false nativeWrite false]
close $::cmcpInventoryF
'''
code=code.replace('PID',str(a.pid)).replace('JSONHELPER',tcl_string((ADAPTERS/'json.tcl').as_posix())).replace('OUTPUT',tcl_string(output.as_posix()));payload.write_text(code,encoding='utf-8');wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8')
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
child=subprocess.Popen([str(exe),str(wrapper)],startupinfo=startup,cwd=root)
end=time.monotonic()+15
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'expectedPid':a.pid,'launcherPid':child.pid,'inventoryAvailable':output.exists(),'designOpenedByProbe':False,'nativeWrite':False,'desktopActionsUsed':False,'captureSha256':sha256(exe)}
if output.exists():report['runtime']=json.loads(output.read_text());assert report['runtime']['pid']==a.pid
if child.poll() is None:
 # This new command-file launcher belongs to this probe; never terminate the observed Capture PID.
 child.terminate();child.wait(timeout=5);report['unacknowledgedLauncherTerminated']=True
else:report['launcherExitCode']=child.returncode
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='runtime'}))
