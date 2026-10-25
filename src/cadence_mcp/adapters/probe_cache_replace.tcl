# Internal owned-fixture probe. No public mutation tool until independent acceptance.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root design specPath output
set f [open $specPath];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase load
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set phase open_design
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 set phase open_library
 set lib [$session GetLibAndSchematics [cmcp::cs [dict get $spec newLib]] $state];cmcp::check $state
 if {$d eq "NULL" || $lib eq "NULL"} {error missing_input}
 set phase replace_cache
 cmcp::check [$d ReplaceCache [cmcp::cs [dict get $spec oldName]] [cmcp::cs [dict get $spec oldLib]] [cmcp::cs [dict get $spec newName]] [cmcp::cs [dict get $spec newLib]] [dict get $spec update] 1]
 set phase save_pages
 set state [DboState];set pages {};set count 0
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v]
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;if {[incr count]>10000} {error page_limit};lappend pages [list $s $p]
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[dict exists $spec restoreReferences]} {
  set phase restore_reference_identity;set targets {};set seen {}
  foreach pair $pages {
   lassign $pair s p;set state [DboState]
   set it [$p NewPartInstsIter $state];cmcp::check $state
   try {
    for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
     cmcp::check $state;if {[incr count]>100000} {error object_limit}
     set id [$part GetId $state];cmcp::check $state
     foreach mapping [dict get $spec restoreReferences] {
      if {$id==[dict get $mapping nativeId]} {
       if {$id in $seen} {error duplicate_native_identity}
       lappend seen $id;lappend targets [list $part $mapping]
      }
     }
    }
   } finally {delete_DboPagePartInstsIter $it}
  }
  if {[llength $targets]!=[llength [dict get $spec restoreReferences]]} {error restore_target_missing}
  foreach pair $targets {
   lassign $pair part mapping
   cmcp::check [$part SetReference [cmcp::cs [dict get $mapping reference]]]
   if {[dict exists $mapping preserveProperties]} {
    dict for {key value} [dict get $mapping preserveProperties] {
     if {$key ni {Value {PCB Footprint}}} {error unsupported_preserved_property}
     cmcp::check [$part SetEffectivePropStringValue [cmcp::cs $key] [cmcp::cs $value]]
    }
   }
  }
 }
 foreach pair $pages {lassign $pair s p;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]}
 set phase save_schematics
 set done {};foreach pair $pages {set s [lindex $pair 0];if {$s ni $done} {cmcp::check [$d SaveSchematic $s];lappend done $s}}
 set phase save_design
 cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
