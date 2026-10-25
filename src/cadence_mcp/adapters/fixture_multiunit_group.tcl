# Fixed library-bound placement on a new isolated output copy only.
source [file join [file dirname [info script]] json.tcl]
package require json
if {$argc!=5} {exit 2}
lassign $argv root design library specPath output
if {[file size $specPath]>65536} {exit 2}
set f [open $specPath];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
set schematicName [dict get $spec schematicName];set pageName [dict get $spec pageName]
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
proc cmcp::pinSignature {part} {
    set state [DboState];set it [$part NewLPinsIter $state];cmcp::check $state;set rows {}
    try {
        for {set pin [$it NextPin $state]} {$pin ne "NULL"} {set pin [$it NextPin $state]} {
            cmcp::check $state;if {[llength $rows]>=256} {error pin_limit}
            set n [cmcp::cs ""];cmcp::check [$pin GetPinName $n]
            set pos [$pin GetPinPosition $state];cmcp::check $state
            set kind [$pin GetPinType $state];cmcp::check $state
            set visible [$pin GetIsVisible $state];cmcp::check $state
            set start [$pin GetStartPoint $state];cmcp::check $state
            set hot [$pin GetHotSpot $state];cmcp::check $state
            lappend rows [list $pos [cmcp::str $n] $kind $visible [DboTclHelper_sGetCPointX $start] [DboTclHelper_sGetCPointY $start] [DboTclHelper_sGetCPointX $hot] [DboTclHelper_sGetCPointY $hot]]
        }
    } finally {delete_DboLibPartPinsIter $it}
    return [lsort $rows]
}
set selectionRows {};set session "";set phase load_dll
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set phase open_design
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error missing_design}
    set phase locate_page
    set matches {};set count 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set view [$vi NextView $state]} {$view ne "NULL"} {set view [$vi NextView $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set schematic [DboViewToDboSchematic $view];set sn [cmcp::cs ""];cmcp::check [$schematic GetName $sn]
            if {[cmcp::str $sn] ne $schematicName} {continue}
            set pi [$schematic NewPagesIter $state];cmcp::check $state
            try {
                for {set page [$pi NextPage $state]} {$page ne "NULL"} {set page [$pi NextPage $state]} {
                    cmcp::check $state
                    if {[incr count]>100000} {error object_limit}
                    set pn [cmcp::cs ""];cmcp::check [$page GetName $pn]
                    if {[cmcp::str $pn] eq $pageName} {lappend matches [list $schematic $page]}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[llength $matches]!=1} {error ambiguous_page}
    lassign [lindex $matches 0] schematic page
    set state [DboState];set phase open_library
    set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
    set source [$lib GetPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
    set sourceSuffixes {};set sourceSignatures {}
    foreach unit [dict get $spec units] {
        set sourceDevice [$source GetDevice [cmcp::cs [dict get $unit designator]] $state];cmcp::check $state
        set sourceCell [$sourceDevice GetCell $state];cmcp::check $state
        set sourceParts [$sourceCell NewPartsIter $state];cmcp::check $state;set matches {}
        try {
            for {set sp [$sourceParts NextPart $state]} {$sp ne "NULL"} {set sp [$sourceParts NextPart $state]} {
                cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$sp GetName $n]
                if {[cmcp::str $n] eq [dict get $unit sourcePartName]} {lappend matches [cmcp::str [$sp GetSuffix]];dict set sourceSignatures [dict get $unit designator] [cmcp::pinSignature $sp]}
            }
        } finally {delete_DboCellPartsIter $sourceParts}
        if {[llength $matches]!=1} {error ambiguous_source_variant}
        dict set sourceSuffixes [dict get $unit designator] [lindex $matches 0]
        set state [DboState]
    }
    set phase copy_package
    set cache [$d CopyPackageAll $source [cmcp::cs [dict get $spec cacheName]] $state];cmcp::check $state
    if {$cache eq "NULL"} {error missing_cache}
    set selectionRows {}
    foreach unit [dict get $spec units] {
        set phase "device_[dict get $unit designator]"
        set device [$cache GetDevice [cmcp::cs [dict get $unit designator]] $state];cmcp::check $state
        set cell [$device GetCell $state];cmcp::check $state
        set pi [$cell NewPartsIter $state];cmcp::check $state;set choices {};set names {}
        try {
            for {set candidate [$pi NextPart $state]} {$candidate ne "NULL"} {set candidate [$pi NextPart $state]} {
                cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$candidate GetName $n];set name [cmcp::str $n];lappend names $name
                if {[cmcp::pinSignature $candidate] eq [dict get $sourceSignatures [dict get $unit designator]]} {lappend choices $candidate}
            }
        } finally {delete_DboCellPartsIter $pi}
        lappend selectionRows [cmcp::obj designator [cmcp::q [dict get $unit designator]] cachedPartNames [cmcp::arr [lmap n $names {cmcp::q $n}]] requestedVariant [cmcp::q [dict get $unit variant]] sourceNativeSuffix [cmcp::q [dict get $sourceSuffixes [dict get $unit designator]]]]
        if {[llength $choices]!=1} {error ambiguous_variant_suffix}
        set phase "place_[dict get $unit designator]"
        set instance [$page NewPlacedInst $state [cmcp::cs [dict get $spec reference]] [cmcp::cs [dict get $spec cacheName]] [lindex $choices 0] $device [DboTclHelper_sMakeCPoint {*}[dict get $unit location]] 0 0];cmcp::check $state
        cmcp::check [$instance SetReference [cmcp::cs [dict get $spec reference]]]
        cmcp::check [$instance SetPartValue [cmcp::cs [dict get $spec packageName]]]
    }
    set phase wiring
    set i 0
    foreach path [dict get $spec wires] {
        set wire [$page NewWireScalar $state [DboTclHelper_sMakeCPoint {*}[lindex $path 0]] [DboTclHelper_sMakeCPoint {*}[lindex $path 1]]];cmcp::check $state
        incr i
        set aliasName ""
        if {[dict exists $spec wireAliases]} {
            if {[dict exists [dict get $spec wireAliases] $i]} {set aliasName [dict get [dict get $spec wireAliases] $i]}
        } elseif {$i==1} {set aliasName VCC}
        if {$aliasName ne ""} {
            set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
            set alias [$wire NewAlias $state [cmcp::cs $aliasName] [DboTclHelper_sMakeCPoint {*}[lindex $path 0]] $font 0 0];cmcp::check $state
        }
    }
    set phase save_page
    cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
    set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true selection [cmcp::arr $selectionRows]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false selection [cmcp::arr $selectionRows] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}

