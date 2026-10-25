# Read actual cached view name of one exact native placed instance.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
if {$argc!=6} {exit 2}
lassign $argv root design output schematicName pageName nativeId
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 lassign [cmcp::qualifiedPage $d $schematicName $pageName] schematic page
 set state [DboState];set it [$page NewPartInstsIter $state];cmcp::check $state;set matches {};set count 0
 try {
  for {set instance [$it NextPartInst $state]} {$instance ne "NULL"} {set instance [$it NextPartInst $state]} {
   cmcp::check $state;if {[incr count]>100000} {error instance_limit}
   set id [$instance GetId $state];cmcp::check $state
   if {$id==$nativeId} {lappend matches $instance}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $matches]!=1} {error ambiguous_instance}
 set state [DboState];set instance [DboPartInstToDboPlacedInst [lindex $matches 0]]
 if {$instance eq "NULL"} {error not_placed}
 set part [$instance GetPart $state];cmcp::check $state
 set name [cmcp::cs ""];cmcp::check [$part GetName $name]
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj partName [cmcp::q [cmcp::str $name]]]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: cached unit view read failed: $message";exit 1}
