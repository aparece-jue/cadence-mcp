# Original isolated acceptance fixture, using official library copy/placement APIs.
if {$argc!=5} {exit 2}
lassign $argv install design library output helper
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
    phase open_source_library
    set lib [$session GetLibAndSchematics [cs $library] $state];check $state
    set source [$lib GetPackage [cs R] $state];check $state
    phase copy_package_and_dependencies
    set pkg [$d CopyPackageAll $source [cs MCP_FIXTURE_R] $state];check $state
    if {$pkg eq "NULL"} {error no_cached_package}
    phase get_cached_device
    set device [$pkg GetDevice [cs ""] $state];check $state
    set cell [$device GetCell $state];check $state
    set iterator [$cell NewPartsIter $state];check $state
    set parts {}
    try {for {set part [$iterator NextPart $state]} {$part ne "NULL"} {set part [$iterator NextPart $state]} {check $state;lappend parts $part}} finally {delete_DboCellPartsIter $iterator}
    if {[llength $parts]!=1} {error ambiguous_cached_part}
    set part [lindex $parts 0]
    foreach {reference x y} {R101 300 300 R102 500 300} {
        phase "place_$reference"
        set instance [$p NewPlacedInst $state [cs $reference] [cs MCP_FIXTURE_R] $part $device [DboTclHelper_sMakeCPoint $x $y]];check $state
        if {$instance eq "NULL"} {error no_instance}
        phase "reference_$reference"
        check [$instance SetReference [cs $reference]]
        check [$instance SetPartValue [cs 1k]]
    }
    phase save_page
    check [$p MarkModified];check [$s MarkModified $p];check [$s SavePage $p]
    phase save_schematic
    check [$d SaveSchematic $s]
    phase save_design
    check [$session MarkAllLibForSave $d];check [$session SaveDesign $d]
    phase saved
    set result [cmcp::obj saved true count 2]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result;close $f;close $log
if {$rc} {exit 1}
