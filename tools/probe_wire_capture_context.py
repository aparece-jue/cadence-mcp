"""Isolated Capture-host wire construction comparison; no real design or desktop action."""
import argparse,csv,json,subprocess,time
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.bridge_rpc import process_image
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument("--pid",type=int,required=True);p.add_argument("--expected-design",type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cfg=Config(a.install_root,root,(root,),45)
rows=list(csv.reader(subprocess.run(['tasklist','/FI','IMAGENAME eq Capture.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=True).stdout.splitlines()))
assert [int(r[1]) for r in rows if r and r[0].lower()=='capture.exe']==[a.pid], 'Explicit single existing Capture required'
exe=(cfg.install_root/'tools/bin/Capture.exe').resolve(strict=True);assert process_image(a.pid)==exe
active=a.expected_design.resolve(strict=True);assert '.local' in active.parts and active.suffix.lower()=='.dsn'
active_before=sha256(active)
expected={'schematics':['ROOT'],'pages':['MAIN'],'wires':[[[100,100],[300,100]]],'parts':0,'pins':0}
write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
source=ADAPTERS/'fixture_wire_page_state.tcl'
code=source.read_text(encoding='utf-8')
load=' load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic'
assert code.count(load)==1
code=code.replace(load,' if {![llength [info commands DboTclHelper_sCreateSession]]} {error database_commands_unavailable}')
code=code.replace('source [file join [file dirname [info script]] json.tcl]','source '+tcl_string((ADAPTERS/'json.tcl').as_posix()),1)
code=code.replace('if {$rc} {exit 1}', 'if {$rc} {error $message}')
fixture=root/'fixture.tcl';fixture.write_text(code,encoding='utf-8')
boot=root/'boot.txt';receipt=root/'receipt.json';wrapper=root/'invoke.tcl'
script='if {[pid] != '+str(a.pid)+'} {error wrong_capture_process}\n'
script+='set cmcpPrior [GetActivePMDesign]\nif {$cmcpPrior eq "NULL" || $cmcpPrior eq ""} {error missing_expected_design}\n'
script+='set cmcpPriorName [DboTclHelper_sMakeCString]\n$cmcpPrior GetName $cmcpPriorName\n'
script+='if {![string equal -nocase [file normalize [DboTclHelper_sGetConstCharPtr $cmcpPriorName]] '+tcl_string(active.as_posix())+']} {error wrong_active_design}\n'
script+='set cmcpBoot [open '+tcl_string(boot.as_posix())+' {WRONLY CREAT EXCL}]\nputs $cmcpBoot [pid]\nclose $cmcpBoot\n'
script+='namespace eval ::cmcpHostWireProbe {\nset argv [list '+ ' '.join(tcl_string(str(v).replace('\\','/')) for v in (cfg.install_root,'default',root,receipt)) +']\nset argc 4\nsource '+tcl_string(fixture.as_posix())+'\n}\n'
wrapper.write_text(script,encoding='utf-8')
report={'passed':False,'scope':'PID and active-private-design bound Capture host; separate Dbo session; no Open/Save active design or desktop action','sourceAdapterSha256':sha256(source),'generatedAdapterSha256':sha256(fixture),'oracleSha256':oracle}
startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,env=process_env(cfg),startupinfo=startup)
end=time.monotonic()+20
while not receipt.exists() and time.monotonic()<end:time.sleep(.1)
process={'launcherPid':child.pid,'expectedCapturePid':a.pid,'receiptAvailable':receipt.exists()}
if child.poll() is None:
 assert child.pid!=a.pid;child.terminate();child.wait(timeout=5);process['ownedForwarderTerminated']=True
else:process['launcherExitCode']=child.returncode
report['process']=process;report['bootAvailable']=boot.exists();report['receiptAvailable']=receipt.exists()
if boot.exists():report['bootPid']=int(boot.read_text().strip())
if receipt.exists():report['receipt']=json.loads(receipt.read_text(encoding='utf-8'))
try:
 assert report.get('bootPid')==a.pid and report['receipt']['saved']
 target=root/'design.dsn';before=sha256(target);report['designSha256']=before
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'))
 assert [s['name'] for s in defs['schematic']]==expected['schematics'] and [p['name'] for p in defs['page']]==expected['pages'] and not defs['part'] and not defs['pin']
 run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(root/'connections.json'),'connections'],root)
 objects=json.loads((root/'connections.json').read_text(encoding='utf-8'))['objects']
 assert [o['attributes']['points'] for o in objects if o['kind']=='wire']==expected['wires'] and all(o['kind']=='wire' for o in objects)
 report['sourceUnchanged']=sha256(target)==before;report['passed']=report['sourceUnchanged']
except Exception as error:report['error']=str(error)
report['activeDesignUnchanged']=sha256(active)==active_before;report['activeDesignSha256']=active_before
report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['oracleUnchanged'] and report['activeDesignUnchanged']
write_json(root/'report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
