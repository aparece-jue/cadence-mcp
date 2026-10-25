# Private constructor/default comparison; all cases keep the same independent wire geometry.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root mode directory output
if {$mode ni {default newpoint0 newpoint1 setpoint0 setpoint1}} {exit 2}
set target [file join $directory design.dsn];if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::phase {directory value} {set f [open [file join $directory phase.txt] w];puts $f $value;close $f}
set phase create;set session "";set details {}
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set enums {};foreach name {::DboValue_DEFAULT_OBJECT_COLOR ::DboValue_DEFAULT_LINE_STYLE ::DboValue_DEFAULT_LINE_WIDTH} {if {[info exists $name]} {lappend enums [cmcp::obj name [cmcp::q $name] value [set $name]]}}
 lappend details defaults [cmcp::arr $enums]
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs ROOT]];cmcp::check $state
 set s [$d GetRootSchematic $state];cmcp::check $state
 set p [$s NewPage $state [cmcp::cs MAIN]];cmcp::check $state
 set a [DboTclHelper_sMakeCPoint 100 100];set b [DboTclHelper_sMakeCPoint 300 100];set phase new_wire
 if {$mode eq "default"} {set w [$p NewWireScalar $state $a $b]} else {set w [$p NewWireScalar $state [expr {[string index $mode end] eq "1" ? 1 : 0}]]}
 cmcp::check $state;if {$w eq "NULL"} {error missing_wire}
 if {$mode ne "default"} {
  cmcp::phase $directory before_points
  if {[string match newpoint* $mode]} {cmcp::check [$w NewPoint $a];cmcp::check [$w NewPoint $b]} else {cmcp::check [$w SetPoint 0 $a];cmcp::check [$w SetPoint 1 $b]}
  cmcp::phase $directory after_points
 }
 cmcp::check $state;if {$w eq "NULL"} {error missing_wire}
 set phase initialize
 set state [DboState];set count [$p GetWireCount $state];cmcp::check $state;lappend details pageWireCount $count
 set phase inspect_created
 set properties {}
 foreach method {GetId GetColor GetLineStyle GetLineWidth GetPointCount} {set state [DboState];set value [$w $method $state];cmcp::check $state;lappend properties [cmcp::obj field [cmcp::q $method] value $value]}
 lappend details wireProperties [cmcp::arr $properties]
 set state [DboState];set pageId [$p GetId $state];lappend details pageId $pageId pageIdCode [$state Code]
 set state [DboState];set net [$w GetNet $state];lappend details wireNetNull [expr {$net eq "NULL" ? "true" : "false"}] wireNetCode [$state Code]
 set name [cmcp::cs ""];set ns [$w GetNetName $name];lappend details wireNetName [cmcp::q [DboTclHelper_sGetConstCharPtr $name]] wireNetNameCode [$ns Code]
 set phase save
 cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p];cmcp::check [$d SaveSchematic $s];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] mode [cmcp::q $mode] details [cmcp::obj {*}$details] error [cmcp::q [expr {$rc ? $message : ""}]]]} finally {close $f}
if {$rc} {exit 1}
