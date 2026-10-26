import argparse,json,time,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_pspice_project import freeze_project,stage_snapshot,validate_snapshot
from cadence_mcp.capture_pspice_receipt import decode_receipt
from cadence_mcp.bridge_rpc import RpcConnection,process_image
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser(description='Real Capture acceptance of internal project staging and nonce-bound netlist backend; no public MCP task claim.')
for name in ('workspace-root','source-root','install-root','binding','expected-netlist','expected-aliases'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();source=a.source_root.resolve(strict=True);expected_net=a.expected_netlist.resolve(strict=True);expected_alias=a.expected_aliases.resolve(strict=True);root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(source,),30);
cap=CaptureService(cfg);ws=cap.create_workspace(str(source/'lowpassfilters.dsn'));sid=cap.open(ws['workspaceId'])['sessionId'];bundle=freeze_project(cfg,cap,sid,str(source/'LowPassFilters.opj'),str(source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim'));job=cfg.workspace_root/'native-job';job.mkdir();paths=stage_snapshot(cfg,bundle,job);cap.close(sid);original={row['path']:row['sha256'] for row in bundle['sources']};staged={role:sha256(Path(path)) for role,path in paths.items()};binding=a.binding.resolve(strict=True);connection=RpcConnection(binding);hello=connection.call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean' and hello['data']['propertyPlanCount']==0;private=json.loads(binding.read_text());active=Path(private['expectedDesign']);active_before=sha256(active);pid=private['expectedPid'];exe=Path(private['expectedExecutable']);assert exe.resolve()==(cfg.install_root/'tools/bin/Capture.exe').resolve() and process_image(pid)==exe.resolve() and sha256(exe)==private['executableFingerprint'];nonce=uuid.uuid4().hex;target=job/'project'/bundle['description']['netlistTarget'];receipt=job/'native-result.json';marker=job/'entered.txt';wrapper=job/'invoke.tcl';code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'capture_pspice_netlist_job.tcl').as_posix())+'\n::cmcpNativeNetlist::run '+ ' '.join(tcl_string(x) for x in [str(pid),active.as_posix(),Path(paths['design']).as_posix(),target.as_posix(),receipt.as_posix(),marker.as_posix(),nonce,(cfg.install_root/'tools/bin/orTclNetlist64.dll').as_posix()])+'\n';wrapper.write_text(code,encoding='utf-8');report={'passed':False,'scope':'Internal project snapshot and native receipt backend, not public MCP task availability','nativeGenerationMcpAvailable':False,'sourceRoles':bundle['description'],'projectSnapshotSha256':sha256(Path(paths['project'])),'originalProjectSha256':original[str(source/'LowPassFilters.opj')],'uiRestorationRemoved':b'GlobalState' not in Path(paths['project']).read_bytes()}
try:
 report['forwarderProcess']=run_owned_process([private['expectedExecutable'],wrapper],job,process_env(cfg),10)
 end=time.monotonic()+15
 while not receipt.exists() and time.monotonic()<end:time.sleep(.1)
 assert receipt.exists(),'No receipt; do not replay'
 raw=json.loads(receipt.read_text(encoding='utf-8'));report['receipt']=decode_receipt(raw,nonce,pid);assert target.is_file() and target.stat().st_size>0;aliases=target.with_suffix('.als');assert aliases.is_file() and aliases.stat().st_size>0
 report['netlistMatchesPriorIndependentParameterAudit']=sha256(target)==sha256(expected_net);report['aliasesMatchPrior14PinAudit']=sha256(aliases)==sha256(expected_alias);assert report['netlistMatchesPriorIndependentParameterAudit'] and report['aliasesMatchPrior14PinAudit']
 report['stagedInputsPreserved']=all(sha256(Path(path))==staged[role] for role,path in paths.items());assert report['stagedInputsPreserved'];validate_snapshot(cfg,bundle)
 before={str(p):sha256(p) for p in [target,aliases,receipt,marker]};repeat=job/'repeat.tcl';repeat_ack=job/'repeat-rejection.json';prefix,invocation=code.split('::cmcpNativeNetlist::run ',1);second=prefix+'set rejected [catch {::cmcpNativeNetlist::run '+invocation.strip()+'} rejection]\nset f [open '+tcl_string(repeat_ack.as_posix())+' {WRONLY CREAT EXCL}];puts $f [cmcp::obj pid [pid] rejected $rejected reason [cmcp::q $rejection]];close $f\n';repeat.write_text(second,encoding='utf-8');report['repeatForwarderProcess']=run_owned_process([private['expectedExecutable'],repeat],job,process_env(cfg),10)
 end=time.monotonic()+5
 while not repeat_ack.exists() and time.monotonic()<end:time.sleep(.1)
 replay=json.loads(repeat_ack.read_text());assert replay=={'pid':pid,'rejected':1,'reason':'already_dispatched'};report['sameNonceRefusalAcknowledgedInHost']=True;assert all(sha256(Path(p))==digest for p,digest in before.items());report['sameNonceReceiptAndOutputsUnchanged']=True
 report['passed']=True
except Exception as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 report['sourcesUnchanged']=all(sha256(Path(p))==digest for p,digest in original.items());after=connection.call('hello',{});report['activeBindingPreserved']=not after['data']['bindingLost'] and after['data']['dirtyState']=='clean' and sha256(active)==active_before;report['passed']=report['passed'] and report['sourcesUnchanged'] and report['activeBindingPreserved'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(root/'snapshot.json').write_text(json.dumps(bundle,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ['passed','error','uiRestorationRemoved','stagedInputsPreserved','netlistMatchesPriorIndependentParameterAudit','sameNonceReceiptAndOutputsUnchanged','sourcesUnchanged','activeBindingPreserved']}))

if not report["passed"]:raise SystemExit(1)
