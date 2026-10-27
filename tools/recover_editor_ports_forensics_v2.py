"""Save only this owned failed fixture for evidence, then restore the unchanged control host."""
import json,time
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_jobs import acquire_guard
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.native_host_fence import read_fence,release
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-ports-20261027';dispatch=json.loads((root/'dispatch-report.json').read_text(encoding='utf-8'));d=r/dispatch['jobDirectory'];target=d/'design.dsn'
assert d.resolve().is_relative_to((r/'.local').resolve())
binding_root=r/'.local/editor-wire-fresh-binding-20261027';binding=binding_root/json.loads((binding_root/'report.json').read_text(encoding='utf-8'))['bindingRelativePath'];b=json.loads(binding.read_text(encoding='utf-8'));owner=json.loads((d/'dispatch-claim.json').read_text(encoding='utf-8'));assert read_fence(binding)==owner
assert process_image(owner['pid'])==Path(b['expectedExecutable']);host=Path(b['expectedDesign']);project=host.with_suffix('.opj');before=(sha256(host),sha256(project));old_receipt=sha256(d/'native-result.json');output=d/'forensic-recovery-v2.json';assert not output.exists()
code='''proc cmcpPortRecover {} {
 set phase guard;set saved false;set restored false
 set failed [catch {
  if {[pid]!=PID || ![string equal -nocase [::cmcpBridge::activeDesign] [file normalize TARGET]]} {error wrong_recovery_context}
  set phase save_owned_partial
  proc cmcpRecoverCk {status} {if {[$status Failed]} {error "save_status_[$status Code]"}}
  set d [GetActivePMDesign];set state [DboState]
  set s [$d GetSchematic [DboTclHelper_sMakeCString ROOT] $state];cmcpRecoverCk $state
  set p [$s GetPage [DboTclHelper_sMakeCString MAIN] $state];cmcpRecoverCk $state
  if {$p ne [GetActivePage]} {error wrong_recovery_page}
  set session $::DboSession_s_pDboSession;DboSession -this $session
  cmcpRecoverCk [$p MarkModified]
  cmcpRecoverCk [$s MarkModified $p]
  cmcpRecoverCk [$s SavePage $p]
  cmcpRecoverCk [$d SaveSchematic $s]
  cmcpRecoverCk [$session MarkAllLibForSave $d]
  cmcpRecoverCk [$session SaveDesign $d]
  set saved true
  if {[::cmcpBridge::dirty] ne "clean"} {error owned_output_still_dirty}
  set phase close_owned_partial;SelectPMItem "Design Resources";CloseProject
  if {[file exists [string cat TARGET lck]]} {error output_lock_remains}
  set phase restore_host
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize HOST]]} {Open PROJECT}
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize HOST]] || [::cmcpBridge::dirty] ne "clean"} {error host_not_restored}
  ::cmcpBridge::lifecycleStart;set restored true;set phase returned
 } message]
 set f [open OUTPUT {WRONLY CREAT EXCL}]
 try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj jobId [cmcp::q NONCE] pid [pid] forensicSaved $saved hostRestored $restored phase [cmcp::q $phase] error [cmcp::q [expr {$failed?$message:""}]]]} finally {close $f}
}
cmcpPortRecover
'''
import re
values=dict(PID=str(owner['pid']),TARGET=tcl_string(target.as_posix()),HOST=tcl_string(host.as_posix()),PROJECT=tcl_string(project.as_posix()),OUTPUT=tcl_string(output.as_posix()),NONCE=tcl_string(owner['jobId']))
code=re.sub(r'\b(PID|TARGET|HOST|PROJECT|OUTPUT|NONCE)\b',lambda m:values[m.group()],code)
payload=d/'forensic-recovery-v2.tcl';payload.write_text(code,encoding='utf-8');invoke=d/'invoke-forensic-recovery-v2.tcl';invoke.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'recovery-work',(root,),30);guard=acquire_guard(binding.parent)
try:
 process=run_owned_process([b['expectedExecutable'],str(invoke)],d,process_env(cfg),10)
 until=time.monotonic()+30
 while not output.exists() and time.monotonic()<until:time.sleep(.1)
 assert output.exists(),'Retain fence: recovery outcome unknown'
 receipt=json.loads(output.read_text(encoding='utf-8'));assert receipt['jobId']==owner['jobId'] and receipt['pid']==owner['pid'];assert receipt['forensicSaved'] and receipt['hostRestored'],receipt
 hello=RpcConnection(binding).call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean'
 assert (sha256(host),sha256(project))==before and sha256(d/'native-result.json')==old_receipt;assert release(binding,owner)
 report=dict(passed=True,process=process,originalFailureReceiptUnchanged=True,ownedPartialSavedForEvidenceOnly=True,outputStillUnverified=True,hostUnchanged=True,fenceReleasedAfterProof=True,targetSha256=sha256(target))
 write_json(root/'forensic-recovery-v2-report.json',report);print(json.dumps(report),flush=True)
finally:guard.close()
