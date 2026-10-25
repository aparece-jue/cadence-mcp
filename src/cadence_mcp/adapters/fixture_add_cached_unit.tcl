# Fixed private missing-device placement from an existing DSN cache, no external OLB.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
package require json
if {$argc!=4} {exit 2}
lassign $argv root design request output
if {[file size $request]>65536} {exit 2}
set f [open $request];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase load
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 set phase locate_page;lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] schematic page
 set state [DboState];set owners {};set conflicts 0;set count 0
 set it [$page NewPartInstsIter $state];cmcp::check $state
 try {
  for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
   cmcp::check $state;if {[incr count]>100000} {error instance_limit}
   if {[$part GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE} {continue}
   set placed [DboPartInstToDboPlacedInst $part];set id [$part GetId $state];cmcp::check $state
   if {$id==[dict get $spec ownerNativeId]} {lappend owners $placed}
   set ref [cmcp::cs ""];cmcp::check [$placed GetReference $ref]
   set unit [cmcp::cs ""];cmcp::check [$placed GetDeviceDesignator $unit]
   if {[cmcp::str $ref] eq [dict get $spec reference] && [cmcp::str $unit] eq [dict get $spec deviceDesignator]} {incr conflicts}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $owners]!=1 || $conflicts} {error missing_owner_or_existing_device}
 set owner [lindex $owners 0];set state [DboState];set package [$owner GetPackage $state];cmcp::check $state
 set name [cmcp::cs ""];cmcp::check [$package GetName $name]
 if {[cmcp::str $name] ne [dict get $spec cacheName]} {error owner_cache_mismatch}
 set name [cmcp::cs ""];cmcp::check [$owner GetReference $name]
 if {[cmcp::str $name] ne [dict get $spec reference]} {error owner_reference_mismatch}
 set phase source_device;set device [$package GetDevice [cmcp::cs [dict get $spec deviceDesignator]] $state];cmcp::check $state
 if {$device eq "NULL"} {error missing_device}
 set cell [$device GetCell $state];cmcp::check $state
 set it [$cell NewPartsIter $state];cmcp::check $state;set matches {};set count 0
 try {
  for {set part [$it NextPart $state]} {$part ne "NULL"} {set part [$it NextPart $state]} {
   cmcp::check $state;if {[incr count]>10000} {error part_limit}
   set name [cmcp::cs ""];cmcp::check [$part GetName $name]
   if {[cmcp::str $name] eq [dict get $spec partName]} {lappend matches $part}
  }
 } finally {delete_DboCellPartsIter $it}
 if {[llength $matches]!=1} {error ambiguous_cached_part}
 set state [DboState];set phase add_unit
 set instance [$page NewPlacedInst $state [cmcp::cs [dict get $spec reference]] [cmcp::cs [dict get $spec cacheName]] [lindex $matches 0] $device [DboTclHelper_sMakeCPoint {*}[dict get $spec location]] [dict get $spec rotation] [dict get $spec mirror]];cmcp::check $state
 if {$instance eq "NULL"} {error missing_instance}
 cmcp::check [$instance SetReference [cmcp::cs [dict get $spec reference]]]
 cmcp::check [$instance SetPartValue [cmcp::cs [dict get $spec value]]]
 cmcp::check [$instance SetEffectivePropStringValue [cmcp::cs {PCB Footprint}] [cmcp::cs [dict get $spec footprint]]]
 set phase save
 cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page];cmcp::check [$d SaveSchematic $schematic];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
 set result [cmcp::obj saved true]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
