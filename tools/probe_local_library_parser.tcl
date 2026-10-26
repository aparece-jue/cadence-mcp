source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
lassign $argv install library pins output
set rc [catch {
 load [file join $install tools bin orPSpiceLibParser64.dll] orPSpiceLibParser
 set value [parseLib $library $pins]
} message]
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;puts $f [cmcp::obj returned [expr {$rc?"false":"true"}] error [cmcp::q [expr {$rc?$message:""}]] value [cmcp::q [expr {$rc?"":$value}]]]} finally {close $f}
if {$rc} {exit 1}
