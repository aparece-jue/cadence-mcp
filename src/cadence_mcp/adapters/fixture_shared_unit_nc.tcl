# Fixed private shared-pin NC guard fixture; never exposed as a public write tool.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_[$s Code]"}}
set session "";set phase load
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 lassign [cmcp::qualifiedPage $d HALFADD MCP_PLACE] sch page
 set state [DboState];set it [$page NewPartInstsIter $state];cmcp::check $state;set targets {};set count 0
 try {
  for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
   cmcp::check $state;if {[incr count]>100000} {error part_limit}
   if {[$part GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE} {continue}
   set placed [DboPartInstToDboPlacedInst $part];set name [cmcp::cs ""];cmcp::check [$placed GetReferenceDesignator $name]
   if {[cmcp::str $name] eq "U501A"} {lappend targets $part}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $targets]!=1} {error ambiguous_unit}
 set part [lindex $targets 0];set state [DboState];set it [$part NewPinsIter $state $::IterDefs_ALL 1];cmcp::check $state;set matches {}
 try {
  for {set pin [$it NextPin $state]} {$pin ne "NULL"} {set pin [$it NextPin $state]} {
   cmcp::check $state;set number [cmcp::cs ""];cmcp::check [$pin GetPinNumber $number]
   if {[cmcp::str $number] eq "8"} {lappend matches $pin}
  }
 } finally {delete_DboPartInstPinsIter $it}
 if {[llength $matches]!=1} {error ambiguous_shared_pin}
 set pin [lindex $matches 0];set state [DboState];set old [$pin GetIsNoConnect $state];cmcp::check $state
 if {$old} {error expected_initial_nc_false}
 set phase set_nc;cmcp::check [$pin SetIsNoConnect 1]
 set phase save;cmcp::check [$page MarkModified];cmcp::check [$sch MarkModified $page];cmcp::check [$sch SavePage $page];cmcp::check [$d SaveSchematic $sch];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
 set result [cmcp::obj saved true]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
