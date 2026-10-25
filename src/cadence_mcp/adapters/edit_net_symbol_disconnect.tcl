# Fixed global/offpage edit diagnostic; only isolated copied designs.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root design specPath output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
if {[file size $specPath]>65536} {exit 2}
set f [open $specPath];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
set kind [dict get $spec kind];if {$kind ni {global offpage}} {exit 2}
set session "";set phase load
set log [open [file join [file dirname $output] phases.log] {WRONLY CREAT EXCL}]
proc cmcp::tracePhase {args} {global phase log;puts $log $phase;flush $log}
trace add variable phase write cmcp::tracePhase
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set phase open_design;set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 if {$d eq "NULL"} {error missing_input}
 set matches {};set phase locate_page
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set n [cmcp::cs ""];cmcp::check [$s GetName $n]
   if {[cmcp::str $n] ne [dict get $spec schematicName]} {continue}
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$p GetName $n]
     if {[cmcp::str $n] eq [dict get $spec pageName]} {lappend matches [list $s $p]}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error ambiguous_page};lassign [lindex $matches 0] schematic page
 set state [DboState];set phase locate_symbol
 if {$kind eq "global"} {set it [$page NewGlobalsIter $state];set next NextGlobal;set remove delete_DboPageGlobalsIter} else {set it [$page NewOffPageConnectorsIter $state $::IterDefs_ALL];set next NextOffPageConnector;set remove delete_DboPageOffPageConnectorsIter};cmcp::check $state
 set found {};set count 0
 try {
  for {set obj [$it $next $state]} {$obj ne "NULL"} {set obj [$it $next $state]} {
   cmcp::check $state;if {[incr count]>10000} {error symbol_limit}
   set id [$obj GetId $state];cmcp::check $state
   if {$id==[dict get $spec nativeId]} {lappend found $obj}
  }
 } finally {$remove $it}
 if {[llength $found]!=1} {error ambiguous_symbol};set obj [lindex $found 0]
 set n [cmcp::cs ""];cmcp::check [$obj GetName $n]
 set pt [$obj GetLocation $state];cmcp::check $state
 set r [$obj GetRotation $state];cmcp::check $state
 set m [$obj GetMirror $state];cmcp::check $state
 set h [$obj GetOffsetHotSpot $state];cmcp::check $state
 if {[cmcp::str $n] ne [dict get $spec oldName] || [list [DboTclHelper_sGetCPointX $pt] [DboTclHelper_sGetCPointY $pt]] ne [dict get $spec oldLocation] || $r!=[dict get $spec oldRotation] || $m!=[dict get $spec oldMirror] || [list [DboTclHelper_sGetCPointX $h] [DboTclHelper_sGetCPointY $h]] ne [dict get $spec oldHotSpot]} {error stale_symbol}
 set phase mutate_symbol
 switch -- [dict get $spec operation] {
  set_name {cmcp::check [$obj SetName [cmcp::cs [dict get $spec name]]]}
  set_pose {
   set disconnected [$obj Disconnect];puts $log "disconnectResult=$disconnected";flush $log
   cmcp::check [$obj SetMirror [dict get $spec mirror]]
   cmcp::check [$obj SetRotation [dict get $spec rotation]]
   cmcp::check [$obj SetLocation [DboTclHelper_sMakeCPoint {*}[dict get $spec location]]]
  }
  delete {if {$kind eq "global"} {cmcp::check [$page DeleteGlobal $obj]} else {cmcp::check [$page DeleteOffPageConnector $obj]}}
  default {error invalid_operation}
 }
 set phase save_page;cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
 set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;if {$rc} {puts $f [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} else {puts $f [cmcp::obj saved true operation [cmcp::q [dict get $spec operation]]]};close $f
if {$rc} {exit 1}

