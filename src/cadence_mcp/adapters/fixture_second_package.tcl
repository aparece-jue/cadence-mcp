# Add a second package referencing the existing cells in an owned library copy.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root target specPath output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session GetLibAndSchematics [cmcp::cs $target] $state];cmcp::check $state
set old [$lib GetPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
set package [$lib NewPackage [cmcp::cs MCP_SECOND] $state];cmcp::check $state
cmcp::check [$package SetReferenceTemplate [cmcp::cs X?]]
cmcp::check [$package SetPCBFootprint [cmcp::cs SECOND_FP]]
foreach dev [dict get $spec devices] {
 set oldDevice [$old GetDevice [cmcp::cs [dict get $dev designator]] $state];cmcp::check $state
 set cell [$oldDevice GetCell $state];cmcp::check $state
 set device [$package NewDevice [cmcp::cs [dict get $dev designator]] [dict get $dev position] $cell $state];cmcp::check $state
 foreach pin [dict get $dev mapping] {
  cmcp::check [$device NewPinNumber [cmcp::cs [dict get $pin number]] [DboTclHelper_sMakeInt [dict get $pin position]] [expr {[dict get $pin shared] ? 1 : 0}] [dict get $pin swapId]]
 }
}
cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj saved true addedPackage [cmcp::q MCP_SECOND]]} finally {close $f}
