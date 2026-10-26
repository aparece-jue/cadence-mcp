source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
lassign $argv root design output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session [DboTclHelper_sCreateSession];set rc [catch {
 set st [DboState];set d [$session CreateDesign $st [cs $design] [cs ROOT]];ck $st
 set st [DboState];set s [$d GetRootSchematic $st];ck $st
 set st [DboState];set p [$s NewPage $st [cs MAIN]];ck $st
 ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message];delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];puts $f [cmcp::obj saved [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]]];close $f
if {$rc} {exit 1}
