# Original wire/alias acceptance fixture. Operates only on a host-created copy.
if {$argc!=4} {exit 2}
lassign $argv install design output helper
source $helper
proc cs {v} {return [DboTclHelper_sMakeCString $v]}
proc check {s} {if {[$s Failed]} {error dbo_error}}
set session "";set phase opening
set log [open "${output}.phases" {WRONLY CREAT EXCL}]
proc phase {text} {global phase log;set phase $text;puts $log $text;flush $log}
set rc [catch {
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cs $design] $state];check $state
    set s [$d GetSchematic [cs HALFADD] $state];check $state
    set p [$s GetPage [cs MCP_PLACE] $state];check $state
    phase create_wire
    set wire [$p NewWireScalar $state [DboTclHelper_sMakeCPoint 330 310] [DboTclHelper_sMakeCPoint 490 310]];check $state
    if {$wire eq "NULL"} {error wire_missing}
    phase create_alias_font
    set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
    phase create_alias
    set alias [$wire NewAlias $state [cs MCP_MIDDLE] [DboTclHelper_sMakeCPoint 330 310] $font 0 0];check $state
    if {$alias eq "NULL"} {error alias_missing}
    phase save_page
    check [$p MarkModified];check [$s MarkModified $p];check [$s SavePage $p]
    phase save_schematic
    check [$d SaveSchematic $s]
    phase save_design
    check [$session MarkAllLibForSave $d];check [$session SaveDesign $d]
    phase saved
    set result [cmcp::obj saved true wireCount 1 aliasCount 1]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result;close $f;close $log
if {$rc} {exit 1}
