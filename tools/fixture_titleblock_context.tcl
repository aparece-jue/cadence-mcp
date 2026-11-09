# Test fixture only: pass a disposable copy of the known three-page titleblock design.
if {$argc != 2} {exit 2}
lassign $argv install design
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {st} {if {[$st Failed]} {error "dbo_[$st Code]"}}
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set st [DboState]
set d [$session GetDesignAndSchematics [cs $design] $st];ck $st
set s [$d GetRootSchematic $st];ck $st
set p [$s GetPage [cs MAIN] $st];ck $st
$p SetPageSizeInfo 5000 4000 100 0
set first [$p GetTitleBlock 1 $st];ck $st
if {$first eq "NULL"} {error missing_titleblock}
ck [$first SetPageCount 3];ck [$first SetPageNumber 1]
set second [$p GetTitleBlock 3 $st];ck $st
if {$second eq "NULL"} {error missing_titleblock}
ck [$second SetPageCount 8];ck [$second SetPageNumber 2]
ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s]
ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
delete_DboSession $session
