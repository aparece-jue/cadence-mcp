# Native SaveDesignAs with Replace=0 on an owned staging copy.
source [file join [file dirname [info script]] json.tcl]
if {$argc != 5} {exit 2}
lassign $argv install source target receipt rootName
if {[file exists $target] || [file exists $receipt]} {exit 2}
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
set session ""
set phase load
set rc [catch {
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set phase open
    set design [$session GetDesignAndSchematics [cmcp::cs $source] $state]; cmcp::check $state
    if {$design eq "NULL"} {error missing_design}
    set root [$design GetRootSchematic $state]; cmcp::check $state
    if {$root eq "NULL"} {error missing_root}
    set name [cmcp::cs ""]
    cmcp::check [$root GetName $name]
    if {[DboTclHelper_sGetConstCharPtr $name] ne $rootName} {error root_changed}
    set phase save_as
    cmcp::check [$session SaveDesignAs $design [cmcp::cs $target] 0]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]
} else {
    set result [cmcp::obj saved true operation [cmcp::q save_as] schematicName [cmcp::q $rootName] name [cmcp::q [file tail $target]]]
}
set stream [open $receipt {WRONLY CREAT EXCL}]
try {fconfigure $stream -encoding utf-8 -translation lf; puts $stream $result} finally {close $stream}
if {$rc} {exit 1}
