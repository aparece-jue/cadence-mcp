"""Host-only, owned Capture CLI command inventory. No design or DRC invocation."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.gui_loader import tcl_string
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
config=Config(a.install_root,root/'work',(root,),60)
pidfile=root/'owned-pid.txt';output=root/'runtime.json';payload=root/'inventory.tcl';wrapper=root/'invoke.tcl'
code='''# Fixed host runtime inventory. Never execute a DRC or mutate a design.
set ::cmcpProbeExpectedFile [open PIDFILE r]
set ::cmcpProbeExpected [string trim [read $::cmcpProbeExpectedFile]]
close $::cmcpProbeExpectedFile
if {[pid] != $::cmcpProbeExpected} {error wrong_capture_process}
source JSONHELPER
set ::cmcpProbeRows {}
foreach ::cmcpProbeName [lsort -unique [concat [info commands *DRC*] [info commands *Drc*] [info commands *drc*]]] {
    set ::cmcpProbeArgs null
    if {[llength [info procs $::cmcpProbeName]]} {
        set ::cmcpProbeValues {}
        foreach ::cmcpProbeArg [info args $::cmcpProbeName] {lappend ::cmcpProbeValues [cmcp::q $::cmcpProbeArg]}
        set ::cmcpProbeArgs [cmcp::arr $::cmcpProbeValues]
    }
    lappend ::cmcpProbeRows [cmcp::obj name [cmcp::q $::cmcpProbeName] procedureArgs $::cmcpProbeArgs]
}
set ::cmcpProbeF [open OUTPUT {WRONLY CREAT EXCL}]
try {
    fconfigure $::cmcpProbeF -encoding utf-8 -translation lf
    puts -nonewline $::cmcpProbeF [cmcp::obj pid [pid] tclVersion [cmcp::q [info patchlevel]] commands [cmcp::arr $::cmcpProbeRows] drcExecuted false designOpenedByProbe false]
} finally {close $::cmcpProbeF}
exit 0
'''
for key,value in {'PIDFILE':pidfile,'JSONHELPER':ADAPTERS/'json.tcl','OUTPUT':output}.items():code=code.replace(key,tcl_string(value.as_posix()))
payload.write_text(code,encoding='utf-8');wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8')
def started(pid):pidfile.write_text(str(pid),encoding='ascii')
process=run_owned_process([str(config.install_root/'tools/bin/Capture.exe'),str(wrapper)],root,process_env(config),45,on_started=started)
report={'process':process,'captureSha256':sha256(config.install_root/'tools/bin/Capture.exe'),
        'runtimeInventoryAvailable':output.exists(),'drcExecuted':False,'designOpenedByProbe':False,'desktopActionsUsed':False}
if output.exists():report['runtime']=json.loads(output.read_text(encoding='utf-8'))
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
