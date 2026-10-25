# Fixed owned-fixture global/offpage placement from a copied official OLB.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2}
lassign $argv root design library specPath output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
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
 set phase open_library;set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 if {$d eq "NULL" || $lib eq "NULL"} {error missing_input}
 set matches {};set phase locate_page
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set n [cmcp::cs ""];cmcp::check [$s GetName $n]
   if {[cmcp::str $n] ne "HALFADD"} {continue}
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$p GetName $n]
     if {[cmcp::str $n] eq "MCP_PLACE"} {lappend matches [list $s $p]}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error ambiguous_page};lassign [lindex $matches 0] schematic page
 set state [DboState];set phase source_symbol
 if {$kind eq "global"} {set symbol [$lib GetGlobalSymbol [cmcp::cs [dict get $spec symbol]] $state]} else {set symbol [$lib GetOffPageSymbol [cmcp::cs [dict get $spec symbol]] $state]};cmcp::check $state
 if {$symbol eq "NULL"} {error missing_symbol}
 set phase copy_symbol
 set copied [$d CopySymbol $symbol [cmcp::cs MCP_NETSYM] $state];cmcp::check $state
 if {$copied eq "NULL"} {error copy_failed}
 set phase typed_symbol
 if {$kind eq "global"} {set copied [$d GetGlobalSymbol [cmcp::cs MCP_NETSYM] $state]} else {set copied [$d GetOffPageSymbol [cmcp::cs MCP_NETSYM] $state]};cmcp::check $state
 if {$copied eq "NULL"} {error missing_copied_symbol}
 set phase place_symbol
 set pt [DboTclHelper_sMakeCPoint {*}[dict get $spec location]]
 if {$kind eq "global"} {set obj [$page NewGlobal $state [cmcp::cs [dict get $spec name]] $copied $pt [dict get $spec rotation] [dict get $spec mirror]]} else {set obj [$page NewOffPageConnector $state [cmcp::cs [dict get $spec name]] $copied $pt [dict get $spec rotation] [dict get $spec mirror]]};cmcp::check $state
 if {$obj eq "NULL"} {error no_symbol_instance}
 if {[dict exists $spec wireLead] && [dict get $spec wireLead]} {
  set phase create_wire_lead
  set wire [$page NewWireScalar $state [DboTclHelper_sMakeCPoint 240 310] [DboTclHelper_sMakeCPoint 290 310]];cmcp::check $state
  if {$wire eq "NULL"} {error no_lead_wire}
 }
 set phase save_page;cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
 set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
