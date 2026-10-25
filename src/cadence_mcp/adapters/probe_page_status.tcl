# Private read-only diagnostic: preserve actual native status text at each page-load step.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv root design output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::status {stage state null} {
 set message [cmcp::cs ""];set extended "";set decodeError ""
 if {[catch {$state Message $message} problem]} {set decodeError $problem}
 catch {set extended [DboTclHelper_sGetConstCharPtr [$state GetExtendedText]]}
 return [cmcp::obj stage [cmcp::q $stage] code [$state Code] failed [$state Failed] severity [$state Severity] null $null message [cmcp::q [DboTclHelper_sGetConstCharPtr $message]] extended [cmcp::q $extended] decodeError [cmcp::q $decodeError]]
}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set rows {};set iterator ""
set rc [catch {
 set state [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]
 lappend rows [cmcp::status open_design $state [expr {$d eq "NULL" ? "true" : "false"}]]
 if {[$state Failed] || $d eq "NULL"} {error open_failed}
 set state [DboState];set s [$d GetRootSchematic $state]
 lappend rows [cmcp::status root_schematic $state [expr {$s eq "NULL" ? "true" : "false"}]]
 if {[$state Failed] || $s eq "NULL"} {error schematic_failed}
 set state [DboState];set iterator [$s NewPagesIter $state]
 lappend rows [cmcp::status new_pages_iterator $state [expr {$iterator eq "NULL" ? "true" : "false"}]]
 if {[$state Failed]} {error iterator_failed}
 set state [DboState];set page [$iterator NextPage $state]
 lappend rows [cmcp::status next_page $state [expr {$page eq "NULL" ? "true" : "false"}]]
} message]
if {$iterator ne ""} {catch {delete_DboSchematicPagesIter $iterator}}
catch {delete_DboSession $session}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj rows [cmcp::arr $rows] probeError [cmcp::q [expr {$rc ? $message : ""}]]]} finally {close $f}
