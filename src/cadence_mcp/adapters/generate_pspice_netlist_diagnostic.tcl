# Fixed private native netlist diagnostic with explicit mode and native log vectors.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2};lassign $argv root design target mode output
if {$mode ni {minimal legacy}} {exit 2};if {[file exists $target]} {exit 2}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
load [file join $root tools bin orTclNetlist64.dll] orTclNetlist
set rc [catch {
 if {$mode eq "minimal"} {set result [OrTclNetlist_sCreatePSpiceNetList $design $target]} else {set result [OrTclNetlist_sCreatePSpiceNetList $design $target false true false false true true ""]}
} message]
set logs {}
foreach {name command} {errors OrTclNetlist_sGetErrorLog warnings OrTclNetlist_sGetWarningLog session OrTclNetlist_sGetSessionLog netlist OrTclNetlist_sGetNetlistLog} {
 set vec [DboTclHelper_sMakeStdVector];set code [catch {$command $vec} logError];set values {}
 if {!$code} {set size [DboTclHelper_sGetVectorSize $vec];if {$size>10000} {error log_limit};for {set i 0} {$i<$size} {incr i} {lappend values [cmcp::q [string range [DboTclHelper_sGetConstCharPtrFromVector $vec $i] 0 2047]]}}
 lappend logs [cmcp::obj category [cmcp::q $name] readable [expr {$code ? "false" : "true"}] error [cmcp::q [expr {$code ? $logError : ""}]] lines [cmcp::arr $values]]
}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj invocationReturned [expr {$rc ? "false" : "true"}] nativeReturn [cmcp::q [expr {$rc ? "" : $result}]] error [cmcp::q [expr {$rc ? $message : ""}]] logs [cmcp::arr $logs]];close $f
if {$rc} {exit 1}
