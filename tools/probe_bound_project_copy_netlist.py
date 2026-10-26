"""One fixed local PSpice NET call in an authenticated private Capture host; never retry a dispatch."""
import argparse,json,re,subprocess,time
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS
p=argparse.ArgumentParser()
for n in ('binding','workspace-root','install-root'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument("--oracle",type=Path)
p.add_argument("--source",type=Path,required=True)
p.add_argument("--source-revision",required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);binding=json.loads(a.binding.read_text(encoding='utf-8'));hello=RpcConnection(a.binding).call('hello',{});assert not hello['data']['bindingLost'];exe=Path(binding['expectedExecutable']);assert process_image(binding['expectedPid'])==exe;active=Path(binding['expectedDesign']);active_before=sha256(active);assert hello['data']['dirtyState']=='clean' and hello['data']['propertyPlanCount']==0;source=a.source.resolve(strict=True);assert sha256(source)==a.source_revision;assert '.local' in source.parts and '.local' in root.parts;before=sha256(source)
project=source.with_suffix('.opj');assert project.is_file(), 'Private DSN requires its same-stem OPJ before native export';project_before=sha256(project)
oracle_hash=None
if a.oracle:
 oracle_data=json.loads(a.oracle.read_text(encoding='utf-8'));assert oracle_data['sourceFingerprint']==before;oracle_hash=sha256(a.oracle)
target=root/'generated.net';output=root/'native-result.json';boot=root/'entered.txt';assert not target.exists()
code='''if {[pid]!=PID} {error wrong_process}
source JSON
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize @ACTIVE@]]} {error wrong_active_design}
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
literals={'PID':str(binding['expectedPid']),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'DESIGN':tcl_string(source.as_posix()),'TARGET':tcl_string(target.as_posix()),'OUTPUT':tcl_string(output.as_posix()),'BOOT':tcl_string(boot.as_posix()),'DLL':tcl_string((a.install_root/'tools/bin/orTclNetlist64.dll').as_posix())}
literals['ACTIVE']=tcl_string(active.as_posix())
code=code.replace('@ACTIVE@','ACTIVE')
code=re.sub(r'\b(PID|JSON|DESIGN|TARGET|OUTPUT|BOOT|DLL|ACTIVE)\b',lambda match:literals[match.group(0)],code)
payload=root/'probe.tcl';payload.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=startup);end=time.monotonic()+30
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'scope':'Fixed private copied DSN export inside authenticated host; active project identity and file preserved; no GUI switch requested','sourceSha256':before,'expectedPid':binding['expectedPid'],'launcherPid':child.pid,'acknowledged':output.exists(),'entered':boot.exists(),'targetAbsentBefore':True,'noReplay':True,'oracleSha256':oracle_hash}
if child.poll() is None:assert child.pid!=binding['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['launcherExitCode']=child.returncode
if output.exists():report['receipt']=json.loads(output.read_text(encoding='utf-8'))
report['targetSize']=target.stat().st_size if target.exists() else None
if target.exists():report['targetSha256']=sha256(target)
report['sourceProjectSha256']=project_before;report['sourceProjectUnchanged']=sha256(project)==project_before;report['activeDesignUnchanged']=sha256(active)==active_before;after=RpcConnection(a.binding).call('hello',{});report['activeBindingPreserved']=not after['data']['bindingLost'] and after['data']['dirtyState']=='clean';report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=not a.oracle or sha256(a.oracle)==oracle_hash;report['nonemptyNetProduced']=bool(report['acknowledged'] and report['targetSize']);report['explicitDifferentSource']=source!=active;report['sourceRevision']=before;report['sidecars']={p.suffix:{'size':p.stat().st_size,'sha256':sha256(p)} for p in root.glob('generated.*') if p.is_file()};(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'acknowledged':report['acknowledged'],'entered':report['entered'],'targetSize':report['targetSize'],'sourceUnchanged':report['sourceUnchanged'],'receipt':report.get('receipt')},ensure_ascii=True),flush=True)

report['passed']=bool(report['nonemptyNetProduced'] and report['receipt']['nativeReturn']=='1' and report['receipt']['invocationReturned'] and report['activeDesignUnchanged'] and report['activeBindingPreserved'] and report['sourceUnchanged'] and report['sourceProjectUnchanged'] and '.als' in report['sidecars'] and report['sidecars']['.als']['size']>0 and not next(row for row in report['receipt']['logs'] if row['category']=='errors')['lines'])
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise SystemExit(1)
