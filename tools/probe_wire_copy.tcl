# Fixed standalone wire/transaction comparison; only creates a new private DSN.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=5} {exit 2};lassign $argv install directory mode output source
if {$mode ni {direct_loaded copy0 copy1}} {exit 2}
set target [file join $directory design.dsn];if {[file exists $target]} {error preexisting_design}
proc cs {s} {DboTclHelper_sMakeCString $s}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc mark {phase} {global directory;set f [open [file join $directory phases.txt] a];puts $f $phase;close $f}
set session {};set phase load;set details {};set caught [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set phase template;mark $phase
 set src [$session GetDesignAndSchematics [cs $source] $st];ck $st
 set phase source_schematic;mark $phase;set st [DboState];set sr [$src GetSchematic [cs LPFilters] $st];ck $st
 set it [$sr NewPagesIter $st];ck $st
 try {set sp [$it NextPage $st];ck $st} finally {delete_DboSchematicPagesIter $it}
 if {$sp eq "NULL"} {error missing_source_page}
 set it [$sp NewWiresIter $st];ck $st;set template NULL
 try {
  for {set candidate [$it NextWire $st]} {$candidate ne "NULL"} {set candidate [$it NextWire $st]} {
   ck $st
   if {[$candidate GetPointCount $st]!=2} {ck $st;continue};ck $st
   set scalar [DboWireToDboWireScalar $candidate];if {$scalar eq "NULL"} {continue}
   set template $scalar;break

  }
 } finally {delete_DboPageWiresIter $it}
 if {$template eq "NULL"} {error no_two_point_scalar_template}
 lappend details templateId [$template GetId $st];ck $st
 set phase create;mark $phase
 set d [$session CreateDesign $st [cs $target] [cs ROOT]];ck $st
 set s [$d GetRootSchematic $st];ck $st
 set p [$s NewPage $st [cs MAIN]];ck $st
 lappend details transactionBefore [$p IsTransactionInProgress] countBefore [$p GetTransactionCount]
 set phase transaction;mark $phase

 lappend details transactionStarted [$p IsTransactionInProgress] countStarted [$p GetTransactionCount]
 set phase new_wire;mark $phase
 set st [DboState]
 if {$mode eq "direct_loaded"} {set w [$p NewWireScalar $st [DboTclHelper_sMakeCPoint 100 100] [DboTclHelper_sMakeCPoint 300 100]]} else {
  set w [$p NewWireScalar $template $st [expr {$mode eq "copy1"?1:0}]]
 }
 ck $st
 if {$w ne "NULL" && $mode ne "direct_loaded"} {
  ck [$w SetPoint 0 [DboTclHelper_sMakeCPoint 100 100]]
  ck [$w SetPoint 1 [DboTclHelper_sMakeCPoint 300 100]]
 }
 if {$w eq "NULL"} {error missing_wire}
 set st [DboState];lappend details wireCount [$p GetWireCount $st];ck $st
 set phase save_page;mark $phase
 ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p]
 set phase save_schematic;mark $phase;ck [$d SaveSchematic $s]
 set phase save_design;mark $phase;ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
 lappend details transactionAfter [$p IsTransactionInProgress] countAfter [$p GetTransactionCount]
 set phase saved;mark $phase
} message]
if {$session ne {}} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$caught?"false":"true"}] phase [cmcp::q $phase] error [cmcp::q [expr {$caught?$message:{}}]] details [cmcp::obj {*}$details]];close $f
if {$caught} {exit 1}
