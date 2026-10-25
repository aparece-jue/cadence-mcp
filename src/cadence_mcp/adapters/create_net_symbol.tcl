# Fixed source-bound global/offpage creation on new isolated DSN copies only.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2}
lassign $argv root design library specPath output
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
 set phase open_library;set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 if {$d eq "NULL" || $lib eq "NULL"} {error missing_input}
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
 set state [DboState];set phase source_symbol
 if {$kind eq "global"} {set symbol [$lib GetGlobalSymbol [cmcp::cs [dict get $spec symbol]] $state]} else {set symbol [$lib GetOffPageSymbol [cmcp::cs [dict get $spec symbol]] $state]};cmcp::check $state
 if {$symbol eq "NULL"} {error missing_symbol}
 if {[$symbol GetObjectType]!=[dict get $spec symbolType]} {error source_symbol_type_mismatch}
 set checkState [DboState];set it [$d NewSymbolsIter $checkState];cmcp::check $checkState
 try {
  set count 0
  for {set obj [$it NextSymbol $checkState]} {$obj ne "NULL"} {set obj [$it NextSymbol $checkState]} {
   cmcp::check $checkState;if {[incr count]>10000} {error symbol_limit}
   set n [cmcp::cs ""];cmcp::check [$obj GetName $n]
   if {[string equal -nocase [cmcp::str $n] [dict get $spec cacheName]]} {error cache_name_exists}
  }
 } finally {delete_DboLibSymbolsIter $it}
 set phase copy_symbol
 set copied [$d CopySymbol $symbol [cmcp::cs [dict get $spec cacheName]] $state];cmcp::check $state
 if {$copied eq "NULL"} {error copy_failed}
 set phase typed_symbol
 if {$kind eq "global"} {set copied [$d GetGlobalSymbol [cmcp::cs [dict get $spec cacheName]] $state]} else {set copied [$d GetOffPageSymbol [cmcp::cs [dict get $spec cacheName]] $state]};cmcp::check $state
 if {$copied eq "NULL"} {error missing_copied_symbol}
 set phase place_symbol
 set pt [DboTclHelper_sMakeCPoint {*}[dict get $spec location]]
 if {$kind eq "global"} {set obj [$page NewGlobal $state [cmcp::cs [dict get $spec name]] $copied $pt [dict get $spec rotation] [dict get $spec mirror]]} else {set obj [$page NewOffPageConnector $state [cmcp::cs [dict get $spec name]] $copied $pt [dict get $spec rotation] [dict get $spec mirror]]};cmcp::check $state
 if {$obj eq "NULL"} {error no_symbol_instance}
 if {[dict get $spec leadEnabled]} {
  set phase create_wire_lead
  set wire [$page NewWireScalar $state [DboTclHelper_sMakeCPoint {*}[dict get $spec expectedHotSpot]] [DboTclHelper_sMakeCPoint {*}[dict get $spec leadEnd]]];cmcp::check $state
  if {$wire eq "NULL"} {error no_lead_wire}
 }
 set phase save_page;cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
 set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;if {$rc} {puts $f [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} else {puts $f [cmcp::obj saved true operation [cmcp::q create_net_symbol]]};close $f
if {$rc} {exit 1}
