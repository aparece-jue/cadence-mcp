"""Native titleblock definition/pose experiment with frozen source declarations."""
import json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/titleblock-vectors-20261028';root.mkdir(exist_ok=False)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45)
expected={'pages':['MAIN','OTHER','EMPTY'],'symbol':'MCP_TITLE','definitionBounds':[10,20,110,80],'localLine':[[10,20],[110,80]],'text':'标题 Ω 00123\nRevision A','poses':[{'page':'MAIN','name':'DUP_TITLE','location':[200+180*i,200+180*m],'rotationCode':i,'mirrorCode':m} for m in (0,1) for i in range(4)]+[{'page':'OTHER','name':'DUP_TITLE','location':[300,400],'rotationCode':0,'mirrorCode':0}]}
def rotate(p,rotation,mirror):
 x,y=p
 if mirror:x=-x
 return [(x,y),(y,-x),(-x,-y),(-y,x)][rotation]
for pose in expected['poses']:
 corners=[rotate((x,y),pose['rotationCode'],pose['mirrorCode']) for x in (10,110) for y in (20,80)]
 pose['predictedLine']=[[pose['location'][j]+rotate(p,pose['rotationCode'],pose['mirrorCode'])[j]-min(c[j] for c in corners) for j in (0,1)] for p in expected['localLine']]
(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');oracle=sha256(root/'expected.json')
fixture=r'''lassign $argv install target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase load
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session CreateDesign $st [cs $target] [cs ROOT]];ck $st
 set sch [$d GetRootSchematic $st];ck $st
 set phase symbol;set sym [$d NewTitleBlockSymbol [cs MCP_TITLE] $st];ck $st
 set line [$sym NewLine $st [DboTclHelper_sMakeCPoint 10 20] [DboTclHelper_sMakeCPoint 110 80]];ck $st
 set box [$sym NewBox $st [DboTclHelper_sMakeCPoint 10 20] [DboTclHelper_sMakeCPoint 110 80]];ck $st
 set font [DboTclHelper_sMakeLOGFONT Arial -10 0 0 0 400 0 0 0 0 7 0 1 16]
 set text [$sym NewCommentText $st [cs "标题 Ω 00123\nRevision A"] [DboTclHelper_sMakeCRect 20 30 100 50] [DboTclHelper_sMakeCPoint 20 30] $font];ck $st
 ck [$sym MarkModified];ck [$d SaveTitleBlockSymbol $sym]
 foreach pageName {MAIN OTHER EMPTY} {
  set phase page_$pageName;set p [$sch NewPage $st [cs $pageName]];ck $st
  if {$pageName ne "EMPTY"} {
   foreach m {0 1} {foreach i {0 1 2 3} {
    if {$pageName eq "OTHER" && ($m!=0 || $i!=0)} {continue}
    set phase create_title;set obj [$p NewTitleBlock $st $sym [cs DUP_TITLE]];ck $st
    ck [$obj SetMirror $m];ck [$obj SetRotation $i]
    if {$pageName eq "OTHER"} {set x 300;set y 400} else {set x [expr {200+180*$i}];set y [expr {200+180*$m}]}
    ck [$obj SetLocation [DboTclHelper_sMakeCPoint $x $y]]
   }}
  }
  ck [$p MarkModified];ck [$sch MarkModified $p];ck [$sch SavePage $p]
 }
 set phase save;ck [$d SaveSchematic $sch];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] error [cmcp::q [expr {$rc?$message:""}]]];close $f
if {$rc} {exit 1}
'''
script=root/'fixture.tcl';script.write_text(fixture,encoding='utf-8')
# Reuse the established descriptor/control-point procedures, not their output as an oracle.
part=(ADAPTERS/'inspect_part_vectors.tcl').read_text(encoding='utf-8');helpers=part[part.index('proc cmcp::corners'):part.index('set count 0')]
reader='''lassign $argv install design output helper adapters
source $helper
source [file join $adapters dbo_vector_signature.tcl]
source [file join $adapters dbo_vector_json.tcl]
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
'''+helpers+r'''
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 set s [$d GetRootSchematic $st];cmcp::check $st;set rows {}
 foreach pageName {MAIN OTHER EMPTY} {
  set p [$s GetPage [cmcp::cs $pageName] $st];cmcp::check $st
  set it [$p NewTitleBlocksIter $st];cmcp::check $st
  try {for {set obj [$it NextTitleBlock $st]} {$obj ne "NULL"} {set obj [$it NextTitleBlock $st]} {
   cmcp::check $st;set name [cmcp::cs ""];cmcp::check [$obj GetName $name]
   set location [$obj GetLocation $st];cmcp::check $st;set rotation [$obj GetRotation $st];cmcp::check $st;set mirror [$obj GetMirror $st];cmcp::check $st
   set sym [$obj GetSymbol $st];cmcp::check $st;set vt [$sym NewVectorsIter $st $::IterDefs_ALL];cmcp::check $st;set vectors {}
   try {for {set v [$vt NextVector $st]} {$v ne "NULL"} {set v [$vt NextVector $st]} {
    cmcp::check $st;set desc [cmcp::vectorDescriptor $v];set points {}
    foreach point [cmcp::controlPoints $desc] {lappend points [cmcp::arr [cmcp::shapePoint [$obj GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}$point]]]]}
    lappend vectors [cmcp::obj descriptor [cmcp::descriptorJson $desc] pageControlPoints [cmcp::arr $points]]
   }} finally {delete_DboGraphicObjectVectorsIter $vt}
   if {[$st Failed] && [$st Code]!=1022} {error unexpected_vector_end}
   lappend rows [cmcp::obj page [cmcp::q $pageName] name [cmcp::q [cmcp::str $name]] location [cmcp::arr [cmcp::shapePoint $location]] rotationCode $rotation mirrorCode $mirror vectors [cmcp::arr $vectors]]
  }} finally {delete_DboPageTitleBlocksIter $it}
  if {[$st Failed] && [$st Code]!=1022} {error unexpected_titleblock_end}
 }
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;puts $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr $::errorInfo;exit 1}
'''
readerfile=root/'read.tcl';readerfile.write_text(reader,encoding='utf-8');report={'passed':False,'fullC05Accepted':False,'oracleSha256':oracle}
try:
 source=root/'design.dsn';proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,source,root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45);report['createProcess']=proc;assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
 before=sha256(source);run_tcl(cfg,'inspect.tcl',[str(source),str(root/'definitions.json'),'100000'],root)
 proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',readerfile,cfg.install_root,source,root/'vectors.json',ADAPTERS/'json.tcl',ADAPTERS],root,process_env(cfg),45);report['readProcess']=proc;assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
 rows=json.loads((root/'vectors.json').read_text(encoding='utf-8'));report['titleblocks']=len(rows);assert len(rows)==9
 differences=[]
 for pose in expected['poses']:
  obj=next(x for x in rows if x['page']==pose['page'] and x['rotationCode']==pose['rotationCode'] and x['mirrorCode']==pose['mirrorCode'])
  for k in ('name','location','rotationCode','mirrorCode'):
   if obj[k]!=pose[k]:differences.append({'pose':pose,'field':k,'actual':obj[k]})
  assert len(obj['vectors'])==3
  line=next(x for x in obj['vectors'] if x['descriptor'][0]=='line');text=next(x for x in obj['vectors'] if x['descriptor'][0]=='text')
  assert line['descriptor'][1:3]==expected['localLine'];assert text['descriptor'][1]==expected['text']
  if line['pageControlPoints']!=pose['predictedLine']:differences.append({'pose':pose,'field':'pageControlPoints','actual':line['pageControlPoints']})
 report.update(differences=differences,sourceUnchanged=sha256(source)==before,localDescriptorsAndUnicodeAccepted=True,nativeSaveReopenAccepted=True,passed=not differences and sha256(source)==before)
except BaseException:report['error']=traceback.format_exc()
report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=True),flush=True)
raise SystemExit(0 if report['passed'] else 1)
