# Explicit bReturnShared=1: retain each unit shared-pin definition row.
# Read-only page-definition pin/wire partitions, grouping native GetNet objects.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
namespace eval cmcp {variable ids {};variable rows {};variable count 0}
proc cmcp::group {owner} {
 variable ids;set ns [DboState];set net [$owner GetNet $ns]
 if {$net eq "NULL"} {
  if {[$ns Failed] && [$ns Code]!=1021} {error unknown_null_net}
  return [list null ""]
 }
 cmcp::check $ns
 if {![dict exists $ids $net]} {dict set ids $net "net-[expr {[dict size $ids]+1}]"}
 set n [cmcp::cs ""];cmcp::check [$net GetNetName $n]
 return [list [cmcp::q [dict get $ids $net]] [cmcp::str $n]]
}
proc cmcp::tick {} {variable count;if {[incr count]>100000} {error object_limit}}
set session "";set phase open
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 if {$d eq "NULL"} {error missing_design}
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set sn [cmcp::cs ""];cmcp::check [$s GetName $sn]
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set pn [cmcp::cs ""];cmcp::check [$p GetName $pn]
     # Page nets never merge by equal text across different pages.
     set cmcp::ids {}
     set phase pins;set it [$p NewPartInstsIter $state];cmcp::check $state
     try {
      for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
       cmcp::check $state;cmcp::tick;set ref [cmcp::cs ""]
       if {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE} {cmcp::check [[DboPartInstToDboPlacedInst $part] GetReferenceDesignator $ref]} else {cmcp::check [$part GetReference $ref]}
       set pins [$part NewPinsIter $state $::IterDefs_ALL 1];cmcp::check $state
       try {
        for {set pin [$pins NextPin $state]} {$pin ne "NULL"} {set pin [$pins NextPin $state]} {
         cmcp::check $state;cmcp::tick;set number [cmcp::cs ""];set nstate [$pin GetPinNumber $number]
         if {[$nstate Failed] && [$nstate Code]!=1021} {cmcp::check $nstate}
         set name [cmcp::cs ""];cmcp::check [$pin GetPinName $name];lassign [cmcp::group $pin] group netname
         lappend cmcp::rows [cmcp::obj kind [cmcp::q pin] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pn]] reference [cmcp::q [cmcp::str $ref]] number [cmcp::q [cmcp::str $number]] name [cmcp::q [cmcp::str $name]] group $group netName [cmcp::q $netname]]
        }
       } finally {delete_DboPartInstPinsIter $pins}
      }
     } finally {delete_DboPagePartInstsIter $it}
     set state [DboState];set phase wires;set it [$p NewWiresIter $state];cmcp::check $state
     try {
      for {set w [$it NextWire $state]} {$w ne "NULL"} {set w [$it NextWire $state]} {
       cmcp::check $state;cmcp::tick;set n [$w GetPointCount $state];cmcp::check $state
       if {$n<2 || $n>256} {error wire_shape_limit}
       set pts {}
       for {set i 0} {$i<$n} {incr i} {set q [$w GetPoint $i $state];cmcp::check $state;lappend pts [cmcp::arr [list [DboTclHelper_sGetCPointX $q] [DboTclHelper_sGetCPointY $q]]]}
       set id [$w GetId $state];cmcp::check $state;lassign [cmcp::group $w] group netname
       if {$group eq "null"} {error missing_wire_net}
       lappend cmcp::rows [cmcp::obj kind [cmcp::q wire] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pn]] nativeId $id points [cmcp::arr $pts] group $group netName [cmcp::q $netname]]
      }
     } finally {delete_DboPageWiresIter $it}
     set state [DboState]
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $cmcp::rows];close $f
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
 set f [open "$output.error.json" {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8
 puts $f [cmcp::obj phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]] stack [cmcp::q [string range [dict get $options -errorinfo] 0 2047]]];close $f
 puts stderr "CADENCE_DBO_ERROR: $phase $message";exit 1
}
