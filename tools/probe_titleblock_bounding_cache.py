"""Native titleblock bounding-cache diagnostic on a private copy; never saves."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for name in ('install-root','source','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(exist_ok=False);before=sha256(a.source);target=root/'design.dsn';shutil.copyfile(a.source,target)
code=r'''lassign $argv install design output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}
proc rect {r} {cmcp::arr [concat [pt [DboTclHelper_sGetCRectTopLeft $r]] [pt [DboTclHelper_sGetCRectBottomRight $r]]]}
proc snapshot {obj} {
 set st [DboState];set caught [catch {$obj GetOffsetBoundingBox $st} offset]
 set result [list dirty [$obj IsBoundingBoxDirty] local [rect [$obj GetBoundingBox]] offsetCaught $caught offsetCode [$st Code] offsetFailed [$st Failed]]
 if {!$caught} {lappend result offset [rect $offset]} else {lappend result error [cmcp::q $offset]}
 return [cmcp::obj {*}$result]
}
set session "";set rows {};set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $design] $st];ck $st
 set views [$d NewViewsIter $st $::IterDefs_SCHEMATICS];ck $st
 try {for {set v [$views NextView $st]} {$v ne "NULL"} {set v [$views NextView $st]} {
  ck $st;set sch [DboViewToDboSchematic $v];set pages [$sch NewPagesIter $st];ck $st
  try {for {set page [$pages NextPage $st]} {$page ne "NULL"} {set page [$pages NextPage $st]} {
   ck $st;set titles [$page NewTitleBlocksIter $st];ck $st
   try {for {set obj [$titles NextTitleBlock $st]} {$obj ne "NULL"} {set obj [$titles NextTitleBlock $st]} {
    ck $st;set id [$obj GetId $st];ck $st;set symbol [$obj GetSymbol $st];ck $st;set location [$obj GetLocation $st];ck $st
    set initial [snapshot $obj];set dirtyResult [catch {$obj SetBoundingBoxDirty 1} dirtyMessage];set after [snapshot $obj]
    lappend rows [cmcp::obj nativeId $id location [cmcp::arr [pt $location]] symbolBounds [rect [$symbol GetBoundingBox]] initial $initial dirtyCaught $dirtyResult dirtyMessage [cmcp::q $dirtyMessage] after $after]
   }} finally {delete_DboPageTitleBlocksIter $titles}
  }} finally {delete_DboSchematicPagesIter $pages}
 }} finally {delete_DboLibViewsIter $views}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj caught $rc message [cmcp::q [expr {$rc?$message:""}]] rows [cmcp::arr $rows]];close $f
if {$rc} {exit 1}
''';script=root/'probe.tcl';script.write_text(code,encoding='utf8');cfg=Config(a.install_root,root/'work',(root,),45);process=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',script,a.install_root,target,root/'native.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45);report={'process':process,'saveCalled':False,'sourceSha256':before,'sourceAndCopyUnchanged':sha256(a.source)==before and sha256(target)==before,'native':json.loads((root/'native.json').read_text())};(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report));assert report['sourceAndCopyUnchanged']
