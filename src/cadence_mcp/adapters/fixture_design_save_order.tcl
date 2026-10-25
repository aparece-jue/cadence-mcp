# Minimal owned fresh-design save-order comparison. No existing design is opened.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root mode directory output
if {$mode ni {empty direct initial_design initial_page save_as no_page_save}} {exit 2}
set target [file join $directory design.dsn];if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set phase create;set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs ROOT]];cmcp::check $state
 set s [$d GetRootSchematic $state];cmcp::check $state
 if {$mode eq "initial_design"} {set phase initial_design_save;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]}
 set phase new_page;set p [$s NewPage $state [cmcp::cs MAIN]];cmcp::check $state
 if {$mode eq "initial_page"} {
  set phase initial_page_save
  cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p];cmcp::check [$d SaveSchematic $s];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
 }
 if {$mode ne "empty"} {
  set phase new_wire;set w [$p NewWireScalar $state [DboTclHelper_sMakeCPoint 100 100] [DboTclHelper_sMakeCPoint 300 100]];cmcp::check $state
  if {$w eq "NULL"} {error no_wire}
 }
 set phase save_page;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p]
 if {$mode ne "no_page_save"} {cmcp::check [$s SavePage $p]}
 set phase save_schematic;cmcp::check [$d SaveSchematic $s]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d]
 if {$mode eq "save_as"} {set target [file join $directory final.dsn];cmcp::check [$session SaveDesignAs $d [cmcp::cs $target]]} else {cmcp::check [$session SaveDesign $d]}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] target [cmcp::q $target] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
