# Private constructor/default comparison; all cases keep the same independent wire geometry.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root mode directory output
if {$mode ni {default expand_before expand_after get_root_occurrence}} {exit 2}
set target [file join $directory design.dsn];if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set phase create;set session "";set details {}
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set enums {};foreach name {::DboValue_DEFAULT_OBJECT_COLOR ::DboValue_DEFAULT_LINE_STYLE ::DboValue_DEFAULT_LINE_WIDTH} {if {[info exists $name]} {lappend enums [cmcp::obj name [cmcp::q $name] value [set $name]]}}
 lappend details defaults [cmcp::arr $enums]
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs ROOT]];cmcp::check $state
 set s [$d GetRootSchematic $state];cmcp::check $state
 set p [$s NewPage $state [cmcp::cs MAIN]];cmcp::check $state
 if {$mode eq "expand_before"} {set phase expand_before;cmcp::check [$s Expand]}
 set a [DboTclHelper_sMakeCPoint 100 100];set b [DboTclHelper_sMakeCPoint 300 100];set phase new_wire
 if {$mode ne "init1"} {set w [$p NewWireScalar $state $a $b]} else {
  set version 1
  set junction [expr {$mode eq "junction1" ? 1 : 0}]
  if {$mode in {explicit0 explicit1}} {set color 0;set style 0;set width 0} else {set color $::DboValue_DEFAULT_OBJECT_COLOR;set style $::DboValue_DEFAULT_LINE_STYLE;set width $::DboValue_DEFAULT_LINE_WIDTH}
  set w [$p NewWireScalar $state $a $b $junction $junction $color $version $style $width]
 }
 cmcp::check $state;if {$w eq "NULL"} {error missing_wire}
 set phase initialize
 if {$mode eq "expand_after"} {set phase expand_after;cmcp::check [$s Expand]}
 if {$mode eq "get_root_occurrence"} {set state [DboState];set occurrence [$d GetRootOccurrence $state];lappend details rootOccurrenceNull [expr {$occurrence eq "NULL" ? "true" : "false"}] rootOccurrenceCode [$state Code]}
 if {$mode in {init0 init1}} {cmcp::check [$w ConnectInitialization $a $b]}
 if {$mode eq "connections"} {cmcp::check [$w NewConnection $a 0];cmcp::check [$w NewConnection $b 1]}
 if {$mode eq "clear_created"} {cmcp::check [$w ClearCreatedByDB]}
 if {$mode eq "cleanup"} {$w CleanupQuad}
 if {$mode eq "net_before"} {set net [$p NewNetScalar];if {$net eq "NULL"} {error no_net}}
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
