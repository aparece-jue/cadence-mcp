# Complete source package placed atomically on one qualified private page.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_part_signature.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
package require json
if {$argc!=5} {exit 2}
lassign $argv root design library request output
if {[file size $request]>200000} {exit 2}
set f [open $request];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 200001]];close $f
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
set session "";set phase load
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set units [dict get $spec units];set unitCount [llength $units]
    if {$unitCount<2 || $unitCount>16} {error invalid_group_size}
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    set phase locate_page
    lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] schematic page
    set state [DboState]
    set cacheName [dict get $spec cacheName]
    set it [$d NewPackagesIter $state];cmcp::check $state;set count 0
    try {
        for {set package [$it NextPackage $state]} {$package ne "NULL"} {set package [$it NextPackage $state]} {
            cmcp::check $state;if {[incr count]>100000} {error package_limit}
            set n [cmcp::cs ""];cmcp::check [$package GetName $n]
            if {[string equal -nocase [cmcp::str $n] $cacheName]} {error cache_name_exists}
        }
    } finally {delete_DboLibPackagesIter $it}
    set state [DboState];set phase source_package
    set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
    set source [$lib GetPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
    if {[$source GetSize $state]!=$unitCount} {error source_size_mismatch};cmcp::check $state
    set signatures {};set seen {}
    foreach unit $units {
        set designator [dict get $unit deviceDesignator]
        if {[dict exists $seen $designator]} {error repeated_device};dict set seen $designator 1
        set state [DboState]
        set device [$source GetDevice [cmcp::cs $designator] $state];cmcp::check $state
        if {[$device GetPosition $state]!=[dict get $unit devicePosition]} {error device_position_mismatch};cmcp::check $state
        set cell [$device GetCell $state];cmcp::check $state
        set n [cmcp::cs ""];cmcp::check [$cell GetName $n]
        if {[cmcp::str $n] ne [dict get $unit cellName]} {error cell_identity_mismatch}
        set it [$cell NewPartsIter $state];cmcp::check $state;set matches {};set count 0
        try {
            for {set part [$it NextPart $state]} {$part ne "NULL"} {set part [$it NextPart $state]} {
                cmcp::check $state;if {[incr count]>10000} {error part_limit}
                set n [cmcp::cs ""];cmcp::check [$part GetName $n]
                if {[cmcp::str $n] eq [dict get $unit partName]} {lappend matches $part}
            }
        } finally {delete_DboCellPartsIter $it}
        if {[llength $matches]!=1 || $count!=[dict get $unit sourceCellPartCount]} {error source_view_identity_mismatch}
        dict set signatures $designator [cmcp::partShapeSignature [lindex $matches 0]]
    }
    set state [DboState];set phase copy_package
    set cache [$d CopyPackageAll $source [cmcp::cs $cacheName] $state];cmcp::check $state
    if {$cache eq "NULL" || [$cache GetSize $state]!=$unitCount} {error cache_size_mismatch};cmcp::check $state
    foreach unit $units {
        set designator [dict get $unit deviceDesignator];set phase "select_$designator";set state [DboState]
        set device [$cache GetDevice [cmcp::cs $designator] $state];cmcp::check $state
        if {[$device GetPosition $state]!=[dict get $unit devicePosition]} {error cache_device_position_mismatch};cmcp::check $state
        set cell [$device GetCell $state];cmcp::check $state
        set n [cmcp::cs ""];cmcp::check [$cell GetName $n];set cachedCell [cmcp::str $n]
        set oldName [dict get $unit partName];set cellName [dict get $unit cellName];set wanted $oldName
        if {[string first "$cellName." $oldName]==0} {set wanted "$cachedCell[string range $oldName [string length $cellName] end]"}
        set it [$cell NewPartsIter $state];cmcp::check $state;set parts {};set named {}
        try {
            for {set part [$it NextPart $state]} {$part ne "NULL"} {set part [$it NextPart $state]} {
                cmcp::check $state;if {[llength $parts]>=10000} {error part_limit};lappend parts $part
                set n [cmcp::cs ""];cmcp::check [$part GetName $n]
                if {[cmcp::str $n] eq $wanted || [cmcp::str $n] eq $oldName} {lappend named $part}
            }
        } finally {delete_DboCellPartsIter $it}
        if {[llength $parts]!=[dict get $unit sourceCellPartCount]} {error cached_view_count_mismatch}
        set signature [dict get $signatures $designator]
        if {[llength $named]==1} {
            set part [lindex $named 0]
            if {[cmcp::partShapeSignature $part] ne $signature} {error cached_view_shape_mismatch}
        } elseif {[llength $named]>1} {error ambiguous_cached_variant} else {
            set matches {}
            foreach part $parts {if {[cmcp::partShapeSignature $part] eq $signature} {lappend matches $part}}
            if {[llength $matches]!=1} {error ambiguous_cached_variant}
            set part [lindex $matches 0]
        }
        set state [DboState];set phase "place_$designator"
        set instance [$page NewPlacedInst $state [cmcp::cs [dict get $spec reference]] [cmcp::cs $cacheName] $part $device [DboTclHelper_sMakeCPoint {*}[dict get $unit location]] [dict get $unit rotation] [dict get $unit mirror]];cmcp::check $state
        if {$instance eq "NULL"} {error missing_instance}
        cmcp::check [$instance SetReference [cmcp::cs [dict get $spec reference]]]
        cmcp::check [$instance SetPartValue [cmcp::cs [dict get $spec value]]]
    }
    set phase save_page
    cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
    set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true reference [cmcp::q [dict get $spec reference]] cacheName [cmcp::q $cacheName] unitCount $unitCount]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
