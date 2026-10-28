# Fixed bounded capability/signature diagnostics; does not open or mutate designs.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=2} {exit 2};lassign $argv install output
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set result {};set signatures {};set commands {}
foreach pattern {*DboBaseObjectList* *RefDesQueryObject* DboRefDesAnnotate* DboRefDesQueryHandler* *Make*List*} {
 foreach name [lsort [info commands $pattern]] {if {$name ni $commands} {lappend commands $name}}
}
if {[llength $commands]>512} {error command_budget}
foreach name $commands {
 if {[string match *DboBaseObjectList* $name] || $name in {new_RefDesQueryObject RefDesQueryObject DboRefDesAnnotate_Annotate DboRefDesQueryHandler_AssignRefDesToList DboTclHelper_sMakeDboBaseObjectList}} {
  set failed [catch {$name {*}[lrepeat 32 __signature_probe__]} message]
  if {!$failed} {error unexpected_signature_match}
  lappend signatures $name [cmcp::q $message]
 }
}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj commands [cmcp::arr [lmap x $commands {cmcp::q $x}]] signatures [cmcp::obj {*}$signatures]];close $f
