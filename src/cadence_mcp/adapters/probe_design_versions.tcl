source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv root source output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
set d [$session GetDesignAndSchematics [cmcp::cs $source] $state]
if {[$state Failed] || $d eq "NULL"} {exit 1}
set rows {}
foreach method {GetDataVersion GetDesignDataVersion GetInterfaceVersion} {
 set rc [catch {set value [$session $method]} error]
 lappend rows [cmcp::obj owner [cmcp::q session] field [cmcp::q $method] value [cmcp::q [expr {$rc ? $error : $value}]]]
}
foreach method {GetDataVersion GetSaveAsVersion} {
 set rc [catch {set value [$d $method]} error]
 lappend rows [cmcp::obj owner [cmcp::q design] field [cmcp::q $method] value [cmcp::q [expr {$rc ? $error : $value}]]]
}
set name [cmcp::cs ""];set rc [catch {$d GetDataFormatVersion $name} error]
lappend rows [cmcp::obj owner [cmcp::q design] field [cmcp::q formatVersion] value [cmcp::q [expr {$rc ? $error : [DboTclHelper_sGetConstCharPtr $name]}]]]
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows]} finally {close $f}
