# Private acceptance fault: change only the second declared package footprint.
lassign $argv install target name
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
proc cs {x} {DboTclHelper_sMakeCString $x}
proc check {s} {if {[$s Failed]} {error "native_fault_setup_[$s Code]"}}
set s [DboTclHelper_sCreateSession];set st [DboState]
set lib [$s GetLibAndSchematics [cs $target] $st];check $st
set pkg [$lib GetPackage [cs $name] $st];check $st
if {$pkg eq "NULL"} {error missing_fault_target}
check [$pkg SetPCBFootprint [cs UNEXPECTED_SECOND_PACKAGE_FP]]
check [$s MarkAllLibForSave $lib];check [$s SaveLib $lib]
delete_DboSession $s
