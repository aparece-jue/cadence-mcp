# Test fixture writer for a disposable, native FULLADD copy.
# argv: installRoot copiedDSN markerFile normal|definition-only|deep|fanout
if {$argc != 4} {exit 2}
lassign $argv root design marker mode
if {$mode ni {normal definition-only deep fanout}} {exit 2}
proc ck {st} {if {[$st Failed]} {error "dbo_[$st Code]"}}
proc cs {{text ""}} {DboTclHelper_sMakeCString $text}
proc val {text} {DboTclHelper_sGetConstCharPtr $text}
proc mark {phase} {global marker;set f [open $marker a];puts $f $phase;close $f}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set sess [DboTclHelper_sCreateSession];set st [DboState]
set rc [catch {
 set d [$sess GetDesignAndSchematics [cs $design] $st];ck $st
 set s [$d GetRootSchematic $st];ck $st
 set name [cs];ck [$s GetName $name];if {[val $name] ne "FULLADD"} {error wrong_fixture}
 set p [$s GetPage [cs FULLADD] $st];ck $st
 set it [$p NewPartInstsIter $st];ck $st;set matches {}
 try {
  for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
   ck $st;set name [cs];ck [$part GetReference $name]
   if {[val $name] eq "halfadd_A" && [$part GetObjectType]==$::DboBaseObject_DRAWN_INSTANCE} {lappend matches $part}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $matches]!=1} {error wrong_fixture_block}
 set part [lindex $matches 0];set old [cs];ck [$part GetContentsViewName $old]
 if {[val $old] ne "HALFADD"} {error wrong_original_target}
 mark set_recursive_implementation
 if {$mode in {deep fanout}} {
  # Create the target definitions first, then fill them from the bottom up.
  set layers [expr {$mode eq "deep" ? 65 : 15}]
  set branches [expr {$mode eq "deep" ? 1 : 2}]
  set pages {};set schematics {}
  for {set i 1} {$i<=$layers} {incr i} {
   set st [DboState];set targetName [format DEPTH_%03d $i]
   set ns [$d NewSchematic [cs $targetName] $st];ck $st
   if {$ns eq "NULL"} {error missing_depth_definition}
   set np [$ns NewPage $st [cs MAIN]];ck $st
   if {$np eq "NULL"} {error missing_depth_page}
   lappend schematics $ns;lappend pages $np
  }
  mark save_deep_definitions
  for {set i $layers} {$i>=1} {incr i -1} {
   set ns [lindex $schematics [expr {$i-1}]];set np [lindex $pages [expr {$i-1}]]
   if {$i<$layers} {
    for {set b 1} {$b<=$branches} {incr b} {
     set clone [$np NewDrawnInst [DboPartInstToDboDrawnInst $part] $st];ck $st
     if {$clone eq "NULL"} {error missing_depth_block}
     ck [$clone SetReference [cs [format DEPTH_BLOCK_%03d_%d $i $b]]]
     ck [$clone SetLocation [DboTclHelper_sMakeCPoint [expr {100*$b}] 300]]
     ck [$clone SetContentsViewNameWithoutChangingOccurrences [cs [format DEPTH_%03d [expr {$i+1}]]] 0]
    }
   }
   ck [$np MarkModified];ck [$ns MarkModified $np];ck [$ns SavePage $np];ck [$d SaveSchematic $ns]
  }
  ck [$part SetContentsViewNameWithoutChangingOccurrences [cs DEPTH_001] 0]
 } elseif {$mode eq "normal"} {
  ck [$part SetContentsViewName [cs FULLADD]]
 } else {
  ck [$part SetContentsViewNameWithoutChangingOccurrences [cs FULLADD] 0]
 }
 mark save_page
 ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s]
 mark save_design
 ck [$sess MarkAllLibForSave $d];ck [$sess SaveDesign $d]
 mark saved
} message]
catch {delete_DboSession $sess}
if {$rc} {mark $message;exit 1}
