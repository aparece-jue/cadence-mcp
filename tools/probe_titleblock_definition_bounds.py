"""Create two original isolated titleblock definition controls; never opens an existing design.

The declared rectangle is fixture input, not a measured/rendered bounds oracle.
Actual editor visibility, cache refresh and independent reopen require separate QA.
"""
from pathlib import Path
import json
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
import argparse
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--install-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
r=a.output.resolve();r.mkdir(exist_ok=False)
install=a.install_root.resolve(strict=True);dsn=r/'design.dsn'
expected={'schema':1,'onlyDifference':'symbol definition bounds explicitly declared for DECLARED; UNDECLARED unchanged API defaults','vectorLine':[[-30,10],[140,90]],'vectorBox':[-30,10,140,90],'declaredSymbolBounds':[-30,10,140,90],'pages':['UNDECLARED','DECLARED'],'poses':[{'rotation':i,'mirror':m,'location':[200+180*i,200+180*m]} for m in (0,1) for i in range(4)],'acceptance':'Independent actual rendering and cache observation; declared rectangle is input, not measured glyph/stroke bounds','originalFailedFixtureModified':False}
(r/'expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf8')
code=r'''lassign $argv install target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase load
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session CreateDesign $st [cs $target] [cs ROOT]];ck $st
 set sch [$d GetRootSchematic $st];ck $st
 foreach name {UNDECLARED DECLARED} {
  set phase symbol_$name;set sym [$d NewTitleBlockSymbol [cs $name] $st];ck $st
  set line [$sym NewLine $st [DboTclHelper_sMakeCPoint -30 10] [DboTclHelper_sMakeCPoint 140 90]];ck $st
  set box [$sym NewBox $st [DboTclHelper_sMakeCPoint -30 10] [DboTclHelper_sMakeCPoint 140 90]];ck $st
  if {$name eq "DECLARED"} {ck [$sym SetBoundingBox [DboTclHelper_sMakeCRect -30 10 140 90]]}
  ck [$sym MarkModified];ck [$d SaveTitleBlockSymbol $sym]
  set p [$sch NewPage $st [cs $name]];ck $st
  $p SetPageSizeInfo 9700 7200 100 0
  ck [$p SetTitleBlockDisplayed 0];ck [$p SetTitleBlockPrinted 0]
  foreach m {0 1} {foreach i {0 1 2 3} {
   set phase "pose_${name}_${m}_$i";set obj [$p NewTitleBlock $st $sym [cs $name]];ck $st
   ck [$obj SetMirror $m];ck [$obj SetRotation $i]
   ck [$obj SetLocation [DboTclHelper_sMakeCPoint [expr {200+180*$i}] [expr {200+180*$m}]]]
  }}
  ck [$p MarkModified];ck [$sch MarkModified $p];ck [$sch SavePage $p]
 }
 set phase save;ck [$d SaveSchematic $sch];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;puts $f [cmcp::obj saved [expr {!$rc}] phase [cmcp::q $phase] error [cmcp::q [expr {$rc?$message:""}]]]} finally {close $f}
if {$rc} {exit 1}
'''
p=r/'fixture.tcl';p.write_text(code,encoding='utf8')
cfg=Config(install,r/'work',(r,),45)
proc=run_owned_process([install/'tcltk/bin/tclsh.exe',p,install,dsn,r/'native-create.json',ADAPTERS/'json.tcl'],r,process_env(cfg),45)
report={'process':proc,'native':json.loads((r/'native-create.json').read_text()),'expectedSha256':sha256(r/'expected.json'),'sourceSha256':sha256(dsn) if dsn.exists() else None}
(r/'create-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
(r/'fixture.opj').write_text('(ExpressProject "MCP_B175_DEFINITION_CONTROL" (ProjectVersion "19981106") (SoftwareVersion "24.1") (ProjectType "PCB") (Folder "Design Resources" (Folder "Library") (File "./design.dsn" (Type "Schematic Design"))))\n',encoding='utf8')
print(json.dumps(report))
assert report['native']['saved']
