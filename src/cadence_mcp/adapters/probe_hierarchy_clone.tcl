# Internal fixed fixture operation; no public hierarchy writes until full acceptance.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase opening
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 if {$d eq "NULL"} {error no_design}
 set matches {};set count 0
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set n [cmcp::cs ""];cmcp::check [$s GetName $n]
   if {[cmcp::str $n] ne "FULLADD"} {continue}
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set pn [cmcp::cs ""];cmcp::check [$p GetName $pn]
     if {[cmcp::str $pn] ne "FULLADD"} {continue}
     set it [$p NewPartInstsIter $state];cmcp::check $state
     try {
      for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
       cmcp::check $state;if {[incr count]>10000} {error object_limit}
       set ref [cmcp::cs ""];cmcp::check [$part GetReference $ref]
       if {[cmcp::str $ref] eq "halfadd_C"} {error reference_exists}
       if {[cmcp::str $ref] eq "halfadd_A"} {lappend matches [list $s $p [DboPartInstToDboDrawnInst $part]]}
      }
     } finally {delete_DboPagePartInstsIter $it}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error source_not_unique}
 lassign [lindex $matches 0] s p source
 if {$source eq "NULL"} {error source_not_drawn}
 set state [DboState];set phase clone_block
 set clone [$p NewDrawnInst $source $state];cmcp::check $state
 if {$clone eq "NULL"} {error no_clone}
 set phase set_reference;cmcp::check [$clone SetReference [cmcp::cs halfadd_C]]
 set phase set_location;cmcp::check [$clone SetLocation [DboTclHelper_sMakeCPoint 2000 2000]]
 set phase save_page;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]
 set phase save_schematic;cmcp::check [$d SaveSchematic $s]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
