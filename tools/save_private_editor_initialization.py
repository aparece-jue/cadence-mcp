"""Fixed new-wire test in Capture's actual app-owned session, never delete that session or replay."""
import argparse,json,shutil,subprocess,time
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS,run_tcl
p=argparse.ArgumentParser()
for n in ('binding','workspace-root','install-root','oracle'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);b=json.loads(a.binding.read_text(encoding='utf-8'));h=RpcConnection(a.binding).call('hello',{});assert not h['data']['bindingLost'] ;exe=Path(b['expectedExecutable']);assert process_image(b['expectedPid'])==exe;source=Path(b['expectedDesign']);assert '.local' in source.parts and source.name.lower()=='mcp_view_wire.dsn';expected=json.loads(a.oracle.read_text(encoding='utf-8'));assert expected=={'schematics':['ROOT'],'pages':['MAIN'],'parts':0,'pins':0,'wires':[[[100,100],[300,100]]]};oracle_hash=sha256(a.oracle);before=sha256(source);shutil.copy2(source,root/'before.dsn');output=root/'receipt.json'
code=r'''if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]]} {error source_changed}
namespace eval ::cmcpAppWire {
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc mark {phase} {set f [open PHASE a];puts $f $phase;close $f}
set rc [catch {
 mark entered
 set session $::DboSession_s_pDboSession;DboSession -this $session
 set design [GetActivePMDesign];set st [DboState];set sch [$design GetRootSchematic $st];ck $st
 set st [DboState];set it [$sch NewPagesIter $st];ck $st
 try {set st [DboState];set page [$it NextPage $st];ck $st} finally {delete_DboSchematicPagesIter $it}
 set name [DboTclHelper_sMakeCString];ck [$page GetName $name];if {[DboTclHelper_sGetConstCharPtr $name] ne "MAIN"} {error wrong_page}
 set st [DboState];if {[$page GetWireCount $st]!=0} {error preexisting_wire};ck $st
 if {[GetActivePage] ne $page || [GetActiveView] eq "NULL"} {error target_editor_not_active}
 mark editor_verified
 mark save
 ck [$page MarkModified];ck [$sch MarkModified $page];ck [$sch SavePage $page];ck [$design SaveSchematic $sch];ck [$session MarkAllLibForSave $design];ck [$session SaveDesign $design]
 mark saved
} message]
set f [open OUTPUT {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;puts $f [cmcp::obj pid [pid] saved [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]]]} finally {close $f}
}
'''
for k,v in {'PID':str(b['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'PHASE':tcl_string((root/'phases.txt').as_posix()),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace(k,v)
script=root/'probe.tcl';script.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(script.as_posix())+'\n',encoding='utf-8');si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=si);end=time.monotonic()+30
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'passed':False,'scope':'save editor initialization of empty private fixture only; no new wire; active page identity checked','expectedPid':b['expectedPid'],'acknowledged':output.exists(),'noReplay':True,'sourceBefore':before,'oracleSha256':oracle_hash}
if child.poll() is None:assert child.pid!=b['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
try:
 assert output.exists();report['receipt']=json.loads(output.read_text(encoding='utf-8'));assert report['receipt']['saved'];cfg=Config(a.install_root,root/'work',(source.parent,),45);run_tcl(cfg,'inspect.tcl',[str(source),str(root/'definitions.json'),'100000'],root);defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'));assert [s['name'] for s in defs['schematic']]==['ROOT'] and [s['name'] for s in defs['page']]==['MAIN'] and not defs['part'] and not defs['pin'];run_tcl(cfg,'inspect_page_objects.tcl',[str(source),str(root/'connections.json'),'connections'],root);objects=json.loads((root/'connections.json').read_text(encoding='utf-8'))['objects'];assert not objects;report['passed']=True
except Exception as e:report.update(error=str(e),errorCode=getattr(e,'code',None))
report['sourceAfter']=sha256(source);report['oracleUnchanged']=sha256(a.oracle)==oracle_hash;report['passed']=report['passed'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
