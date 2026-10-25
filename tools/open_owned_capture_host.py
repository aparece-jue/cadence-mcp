"""Open one host-owned private project through documented Open, then bind existing bridge."""
import argparse,json,subprocess,time
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.gui_loader import tcl_string,prepare_loader
from cadence_mcp.bridge_rpc import process_image,RpcConnection
from prepare_gui_bridge import prepare
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','project','design'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--pid',type=int,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);project=a.project.resolve(strict=True);design=a.design.resolve(strict=True);assert project.parent==design.parent and '.local' in project.parts;before=sha256(design);exe=(a.install_root/'tools/bin/Capture.exe').resolve(strict=True);assert process_image(a.pid)==exe
def forward(wrapper,receipt):
 startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=startup);end=time.monotonic()+15
 while not receipt.exists() and time.monotonic()<end:time.sleep(.1)
 row={'launcherPid':child.pid,'receiptAvailable':receipt.exists()}
 if child.poll() is None:
  assert child.pid!=a.pid;child.terminate();child.wait(timeout=5);row['ownedForwarderTerminated']=True
 else:row['launcherExitCode']=child.returncode
 return row
output=root/'opened.json';payload=root/'open.tcl';wrapper=root/'invoke.tcl'
code='''# Fixed private project open; refuse any previously active design.
if {[pid]!=PID} {error wrong_capture_process}
source JSONHELPER
set ::cmcpPrior [GetActivePMDesign]
if {$::cmcpPrior ne "NULL" && $::cmcpPrior ne ""} {error active_design_already_present}
set ::cmcpOpenCode [catch {Open PROJECT} ::cmcpOpenMessage]
set ::cmcpOpened [GetActivePMDesign]
set ::cmcpOpenedPath ""
if {$::cmcpOpened ne "NULL" && $::cmcpOpened ne ""} {set ::cmcpCString [DboTclHelper_sMakeCString];$::cmcpOpened GetName $::cmcpCString;set ::cmcpOpenedPath [file normalize [DboTclHelper_sGetConstCharPtr $::cmcpCString]]}
set ::cmcpF [open OUTPUT {WRONLY CREAT EXCL}]
puts $::cmcpF [cmcp::obj pid [pid] invocationReturned [expr {$::cmcpOpenCode ? "false" : "true"}] activeDesign [cmcp::q $::cmcpOpenedPath] error [cmcp::q [expr {$::cmcpOpenCode ? $::cmcpOpenMessage : ""}]]]
close $::cmcpF
'''
for key,value in {'PID':str(a.pid),'JSONHELPER':tcl_string((ADAPTERS/'json.tcl').as_posix()),'PROJECT':tcl_string(project.as_posix()),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace(key,value)
payload.write_text(code,encoding='utf-8');wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8');report={'sourceBefore':before,'projectFingerprintBefore':sha256(project),'openForwarder':forward(wrapper,output),'bridgeReady':False}
if output.exists():
 opened=json.loads(output.read_text());report['opened']=opened
 if opened['pid']==a.pid and Path(opened['activeDesign']).resolve()==design and sha256(design)==before:
  binding=prepare(root,design,a.pid,False);config,loader,receipt=prepare_loader(binding);report['bridgeForwarder']=forward(loader,receipt)
  if receipt.exists():
   hello=RpcConnection(binding).call('hello',{});report['bridgeReady']=not hello['data']['bindingLost'];report['bridgeHello']={'pid':hello['pid'],'instanceId':hello['instanceId'],'generation':hello['generation'],'data':hello['data']};report['bindingRelativePath']=binding.relative_to(root).as_posix()
report['sourceAfter']=sha256(design);report['sourceUnchanged']=report['sourceAfter']==before;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'bridgeReady':report['bridgeReady'],'sourceUnchanged':report['sourceUnchanged'],'openReceiptAvailable':output.exists()}))
