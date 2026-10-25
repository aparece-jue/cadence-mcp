# Internal scalar NC fixture edit on a new owned copy only.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=6} {exit 2}
lassign $argv root design output number old new
if {$old ni {0 1} || $new ni {0 1} || $old==$new || $number ni {1 2}} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase open
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 set matches {};set count 0
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set n [cmcp::cs ""];cmcp::check [$s GetName $n]
   if {[cmcp::str $n] ne "HALFADD"} {continue}
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$p GetName $n]
     if {[cmcp::str $n] ne "MCP_PLACE"} {continue}
     set it [$p NewPartInstsIter $state];cmcp::check $state
     try {
      for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
       cmcp::check $state;if {[incr count]>10000} {error limit}
       set n [cmcp::cs ""];cmcp::check [$part GetReference $n]
       if {[cmcp::str $n] ne "R101"} {continue}
       set pins [$part NewPinsIter $state];cmcp::check $state
       try {
        for {set pin [$pins NextPin $state]} {$pin ne "NULL"} {set pin [$pins NextPin $state]} {
         cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$pin GetPinNumber $n]
         if {[cmcp::str $n] eq $number} {lappend matches [list $s $p $pin]}
        }
       } finally {delete_DboPartInstPinsIter $pins}
      }
     } finally {delete_DboPagePartInstsIter $it}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error ambiguous_pin}
 lassign [lindex $matches 0] s p pin
 set phase check_old_flag;set state [DboState]
 if {[$pin GetIsNoConnect $state]!=$old} {error old_flag_mismatch};cmcp::check $state
 set phase check_unbound;set ns [DboState];set net [$pin GetNet $ns]
 if {$net ne "NULL"} {error connected_pin_refused}
 if {[$ns Failed] && [$ns Code]!=1021} {error unknown_unbound_status}
 set phase set_flag;cmcp::check [$pin SetIsNoConnect $new]
 set phase save_page;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]
 set phase save_schematic;cmcp::check [$d SaveSchematic $s]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
