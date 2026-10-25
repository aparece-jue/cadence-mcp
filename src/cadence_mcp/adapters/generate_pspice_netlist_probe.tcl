# Fixed original diagnostic on private DSN only; never launches Capture GUI.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root design target output
if {[file exists $target]} {exit 2}
set phase load;set result ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 load [file join $root tools bin orTclNetlist64.dll] orTclNetlist
 set phase create_netlist
 # Runtime native signature: design/output, DRC-marker/legacy/subcircuit/hierarchical/descend/name-preference, license.
 set result [OrTclNetlist_sCreatePSpiceNetList $design $target false false false false true true ""]
 set phase complete
} message]
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj invocationReturned [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] nativeReturn [cmcp::q $result] error [cmcp::q [expr {$rc ? [string range $message 0 2047] : ""}]]];close $f
if {$rc} {exit 1}
