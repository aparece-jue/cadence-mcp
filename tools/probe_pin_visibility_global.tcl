# Private fixed probe: declared symbol visibility transitions, no external designs.
source [file join [file dirname [info script]] json.tcl]
package require json
lassign $argv install target request
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
proc cmcp::cs {x} {DboTclHelper_sMakeCString $x}
proc cmcp::check {st} {if {[$st Failed]} {error "dbo_[$st Code]"}}
set f [open $request];fconfigure $f -encoding utf-8;set spec [json::json2dict [read $f]];close $f
set s [DboTclHelper_sCreateSession];set st [DboState];set lib [$s GetLibAndSchematics [cmcp::cs $target] $st];cmcp::check $st
set pkg [$lib GetPackage [cmcp::cs MCP_VIS] $st];cmcp::check $st
set devices [$pkg NewDevicesIter $st];cmcp::check $st
set device [$devices NextDevice $st];cmcp::check $st;delete_DboPackageDevicesIter $devices
set cell [$device GetCell $st];cmcp::check $st
set parts [$cell NewPartsIter $st];cmcp::check $st;set matches {}
try {
 for {set candidate [$parts NextPart $st]} {$candidate ne "NULL"} {set candidate [$parts NextPart $st]} {
  cmcp::check $st;set name [cmcp::cs ""];cmcp::check [$candidate GetName $name]
  if {[DboTclHelper_sGetConstCharPtr $name] eq "VIS.Normal"} {lappend matches $candidate}
 }
} finally {delete_DboCellPartsIter $parts}
if {[llength $matches]!=1} {error ambiguous_visibility_part};set part [lindex $matches 0];set st [DboState]
set it [$part NewLPinsIter $st];cmcp::check $st;set count 0
try {
 for {set pin [$it NextPin $st]} {$pin ne "NULL"} {set pin [$it NextPin $st]} {
  cmcp::check $st;set position [$pin GetPinPosition $st];cmcp::check $st
  cmcp::check [$pin SetIsVisible [expr {[dict get $spec $position] ? 1 : 0}]];incr count
 }
} finally {delete_DboLibPartPinsIter $it}
if {$count!=16} {error incomplete_visibility_matrix}
cmcp::check [$s MarkAllLibForSave $lib];cmcp::check [$s SaveLib $lib];delete_DboSession $s
