# Root schematic wires -> schematic net -> root occurrence -> flat net. No save.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root design mode output
if {$mode ni {plain update}} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
proc cmcp::pt {v} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $v] [DboTclHelper_sGetCPointY $v]]]}
set session "";set phase open;set rows {};set schematicIds {};set flatIds {}
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 set sch [$d GetRootSchematic $state];cmcp::check $state
 set ro [$d GetRootOccurrence $state];cmcp::check $state
 if {$mode eq "update"} {set phase update_net_ports;cmcp::check [$ro UpdateNetAndPorts]}
 set sn [cmcp::cs ""];cmcp::check [$sch GetName $sn]
 set phase page_iterator;set it [$sch NewPagesIter $state];cmcp::check $state
 try {
  for {set page [$it NextPage $state]} {$page ne "NULL"} {set page [$it NextPage $state]} {
   cmcp::check $state;set pn [cmcp::cs ""];cmcp::check [$page GetName $pn]
   set state [DboState];set phase wire_iterator;set wi [$page NewWiresIter $state];cmcp::check $state
   try {
    for {set wire [$wi NextWire $state]} {$wire ne "NULL"} {set wire [$wi NextWire $state]} {
     cmcp::check $state;if {[llength $rows]>=10000} {error wire_limit}
     set id [$wire GetId $state];cmcp::check $state
     set count [$wire GetPointCount $state];cmcp::check $state;if {$count<2 || $count>256} {error point_limit}
     set points {};for {set i 0} {$i<$count} {incr i} {set pt [$wire GetPoint $i $state];cmcp::check $state;lappend points [cmcp::pt $pt]}
     set phase page_net;set net [$wire GetNet $state];cmcp::check $state;if {$net eq "NULL"} {error missing_page_net}
     set phase schematic_net;set schematicNet [$net GetSchematicNet];if {$schematicNet eq "NULL"} {error missing_schematic_net}
     if {![dict exists $schematicIds $schematicNet]} {dict set schematicIds $schematicNet "schematic-net-[expr {[dict size $schematicIds]+1}]"}
     set phase net_occurrence;set occurrence [$ro GetNetOccurrence $schematicNet $state];cmcp::check $state;if {$occurrence eq "NULL"} {error missing_net_occurrence}
     set phase flat_net;set flat [$occurrence GetFlatNet $state];cmcp::check $state;if {$flat eq "NULL"} {error missing_flat_net}
     if {![dict exists $flatIds $flat]} {dict set flatIds $flat "flat-net-[expr {[dict size $flatIds]+1}]"}
     set name [cmcp::cs ""];cmcp::check [$flat GetName $name]
     set global [$flat GetIsGlobal $state];cmcp::check $state;if {$global ni {0 1}} {error invalid_global_flag}
     lappend rows [cmcp::obj schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pn]] wireNativeId $id points [cmcp::arr $points] schematicGroup [cmcp::q [dict get $schematicIds $schematicNet]] flatGroup [cmcp::q [dict get $flatIds $flat]] flatName [cmcp::q [cmcp::str $name]] isGlobal [expr {$global ? "true" : "false"}]]
    }
   } finally {delete_DboPageWiresIter $wi}
   set state [DboState]
  }
 } finally {delete_DboSchematicPagesIter $it}
 set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows];close $f
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set f [open "$output.error.json" {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f;puts stderr "CADENCE_DBO_ERROR: $phase $message";exit 1}
