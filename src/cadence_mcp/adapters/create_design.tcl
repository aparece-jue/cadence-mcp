# Fixed empty design construction, never opens or overwrites a source design.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root specPath target output
if {[file exists $target]} {exit 2}
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
set session "";set phase create
set rc [catch {
    if {[file size $specPath]>4096} {error spec_limit}
    set f [open $specPath]
    try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 4097]]} finally {close $f}
    set rootName [dict get $spec rootName];set pageName [dict get $spec pageName]
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs $rootName]];cmcp::check $state
    if {$d eq "NULL"} {error missing_design}
    set s [$d GetRootSchematic $state];cmcp::check $state
    if {$s eq "NULL"} {error missing_root}
    set p [$s NewPage $state [cmcp::cs $pageName]];cmcp::check $state
    if {$p eq "NULL"} {error missing_page}
    set phase save
    cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p]
    cmcp::check [$s SavePage $p];cmcp::check [$d SaveSchematic $s]
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set receipt [cmcp::obj saved true operation [cmcp::q create_design]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set receipt [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $receipt} finally {close $f}
if {$rc} {exit 1}
