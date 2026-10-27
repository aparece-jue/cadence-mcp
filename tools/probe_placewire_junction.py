"""Fixed editor-command topology experiment. No public arbitrary Tcl interface."""
import json,subprocess,time,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.bridge_rpc import process_image
from cadence_mcp.environment import ADAPTERS,run_tcl
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.capture_wire import geometry_union,point_on_path
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/placewire-junction-20261027';root.mkdir(exist_ok=False)
source=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.dsn'
assert sha256(source)=='5d852a7683bb3d8b60d20a2505d856fa7c4adcd9d2de2f91b29dada242b926fe'
pid=json.loads((source.parent/'host.json').read_text(encoding='utf-8'))['pid']
install=Path(r'D:\Program Files\Cadence\SPB_24.1');exe=install/'tools/bin/Capture.exe';assert process_image(pid)==exe
# Net equivalence is fixed independently of native generated N000xx names.
groups=[[[[100,100],[300,100]]],[[[100,200],[200,200]],[[200,200],[200,250]]],[[[100,350],[300,350]]],[[[200,300],[200,400]]],[[[400,100],[600,100]],[[500,100],[500,200]]],[[[400,300],[600,300]],[[500,300],[700,300]]],[[[400,500],[450,500]]],[[[460,500],[550,500]]]]
groups[2].extend(groups.pop(3))
oracle={'groups':groups,'expectedGroups':7,'crossingHasJunction':True,'tJoined':True,'overlapJoined':True,'gapSeparated':True}
oracle_path=root/'expected.json';oracle_path.write_text(json.dumps(oracle,indent=2),encoding='utf-8');oracle_hash=sha256(oracle_path)
shutil.copy2(source,root/'before.dsn')
commands=['PlaceJunction 2.0 3.5','EndPlace']
output=root/'receipt.json';phases=root/'phases.txt'
code=r'''if {[pid]!=@PID@} {error wrong_process}
source @JSON@
namespace eval ::cmcpPlaceTopology {
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc mark {p} {set f [open @PHASES@ a];puts $f $p;close $f}
set rc [catch {
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize @SOURCE@]] || [::cmcpBridge::dirty] ne "clean"} {error source_changed}
mark entered
set session $::DboSession_s_pDboSession;DboSession -this $session
set d [GetActivePMDesign];set st [DboState];set s [$d GetSchematic [DboTclHelper_sMakeCString ROOT] $st];ck $st
set st [DboState];set p [$s GetPage [DboTclHelper_sMakeCString MAIN] $st];ck $st
OPage ROOT MAIN
if {[GetActivePage] ne $p || [GetActiveView] eq "NULL"} {error wrong_editor}
@COMMANDS@
mark placed
ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
mark saved
} message]
set f [open @OUTPUT@ {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8
puts $f [cmcp::obj pid [pid] saved [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]]];close $f
}
'''
for k,v in {'PID':str(pid),'JSON':tcl_string((ADAPTERS/'json.tcl').as_posix()),'PHASES':tcl_string(phases.as_posix()),'SOURCE':tcl_string(source.as_posix()),'COMMANDS':'\n'.join(commands),'OUTPUT':tcl_string(output.as_posix())}.items():code=code.replace('@'+k+'@',v)
payload=root/'payload.tcl';payload.write_text(code,encoding='utf-8');wrapper=root/'invoke.tcl';wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8')
si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
child=subprocess.Popen([str(exe),str(wrapper)],cwd=root,startupinfo=si);end=time.monotonic()+30
while not output.exists() and time.monotonic()<end:time.sleep(.1)
report={'passed':False,'noReplay':True,'oracleSha256':oracle_hash,'receiptAvailable':output.exists()}
if child.poll() is None:assert child.pid!=pid;child.terminate();child.wait(timeout=5)
try:
 assert output.exists(),'missing receipt';report['receipt']=json.loads(output.read_text(encoding='utf-8'));assert report['receipt']['saved'],'native call failed'
 cfg=Config(install,root/'work',(source.parent,),45)
 run_tcl(cfg,'inspect.tcl',[str(source),str(root/'definitions.json'),'100000'],root)
 defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'));assert not defs['part'] and not defs['pin'] and len(defs['page'])==1
 run_tcl(cfg,'inspect_page_objects.tcl',[str(source),str(root/'connections.json'),'connections'],root)
 objects=json.loads((root/'connections.json').read_text(encoding='utf-8'))['objects'];wires=[o for o in objects if o['kind']=='wire'];assert len(wires)==len(objects),'unexpected nonwire objects'
 assert geometry_union([w['attributes']['points'] for w in wires])==geometry_union([p for g in groups for p in g]),'geometry differs'
 actual=[]
 for group in groups:
  hits=[]
  for wire in wires:
   path=wire['attributes']['points']
   if all(any(point_on_path(pt,p) for p in group) for pt in path) and geometry_union([path])!=[]:hits.append(wire['attributes']['net'])
  assert hits and all(hits) and len(set(hits))==1,'expected group not connected'
  actual.append(hits[0])
 report['actualGroupNets']=actual
 assert len(set(actual))==len(groups),'unintended group merge'
 report['passed']=True
except Exception as error:report.update(error=str(error),errorCode=getattr(error,'code',None))
report['oracleUnchanged']=sha256(oracle_path)==oracle_hash;report['sourceAfter']=sha256(source)
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
