"""Owned Capture host bootstrap inventory; no design opened or business call."""
import argparse,csv,json,subprocess
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.gui_loader import tcl_string
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45)
rows=list(csv.reader(subprocess.run(['tasklist','/FI','IMAGENAME eq Capture.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True).stdout.splitlines()))
if any(r and r[0].lower()=='capture.exe' for r in rows):raise RuntimeError('Existing Capture process; use a matching private binding instead of new launch.')
boot=root/'bootstrap-pid.txt';output=root/'runtime.json';script=root/'inventory.tcl';wrapper=root/'invoke.tcl'
code='''# Host runtime inventory only. No project/design is opened by this script.
set ::cmcpBoot [open BOOT {WRONLY CREAT EXCL}]
puts $::cmcpBoot [pid]
close $::cmcpBoot
source JSONHELPER
set ::cmcpRows {}
foreach ::cmcpCommand [lsort -unique [concat [info commands *PSpice*] [info commands *pspice*] [info commands *Netlist*] [info commands *NetList*] [info commands *Open*] [info commands *DRC*]]] {
 set ::cmcpArgs null
 if {[llength [info procs $::cmcpCommand]]} {set ::cmcpArgList {};foreach ::cmcpArg [info args $::cmcpCommand] {lappend ::cmcpArgList [cmcp::q $::cmcpArg]};set ::cmcpArgs [cmcp::arr $::cmcpArgList]}
 lappend ::cmcpRows [cmcp::obj name [cmcp::q $::cmcpCommand] procedureArgs $::cmcpArgs]
}
set ::cmcpFile [open OUTPUT {WRONLY CREAT EXCL}]
puts $::cmcpFile [cmcp::obj pid [pid] tclVersion [cmcp::q [info patchlevel]] commands [cmcp::arr $::cmcpRows] designOpenedByProbe false netlistExecuted false]
close $::cmcpFile
exit 0
'''
for key,value in {'BOOT':boot,'JSONHELPER':ADAPTERS/'json.tcl','OUTPUT':output}.items():code=code.replace(key,tcl_string(value.as_posix()))
script.write_text(code,encoding='utf-8');wrapper.write_text('source '+tcl_string(script.as_posix())+'\n',encoding='utf-8')
process=run_owned_process([str(cfg.install_root/'tools/bin/Capture.exe'),str(wrapper)],root,process_env(cfg),45)
report={'process':process,'captureSha256':sha256(cfg.install_root/'tools/bin/Capture.exe'),'bootstrapReached':boot.exists(),'inventoryAvailable':output.exists(),'designOpenedByProbe':False,'netlistExecuted':False,'desktopActionsUsed':False}
if boot.exists():report['observedScriptPid']=int(boot.read_text().strip());report['expectedProcessMatchesScriptPid']=report['observedScriptPid']==process['pid']
if output.exists():report['runtime']=json.loads(output.read_text(encoding='utf-8'))
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='runtime'}))
