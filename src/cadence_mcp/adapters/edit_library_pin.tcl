# Fixed isolated library pin edit; derived from this repository's own bounded library traversal.
# argv: installRoot copiedOLB outputJSON maxObjects
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_pin_style.tcl]
namespace eval cmcp {variable count 0; variable limit 100000}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error"}}
proc cmcp::tick {} {variable count; variable limit; if {[incr count] > $limit} {error "object_limit"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
if {$argc != 4} {exit 2}
lassign $argv root source specPath output
if {[file size $specPath]>65536} {exit 2}
set f [open $specPath]
try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
foreach key {targetPin expectedName expectedNumber expectedType expectedPosition changeName newName changeNumber newNumber changeType newType} {set $key [dict get $spec $key]}
set changeStartPoint 0
if {[dict exists $spec changeStartPoint]} {
    foreach key {changeStartPoint newStartPoint expectedStartPoint} {set $key [dict get $spec $key]}
    if {![string is boolean -strict $changeStartPoint]} {exit 2}
    foreach point [list $newStartPoint $expectedStartPoint] {
        if {[llength $point]!=2} {exit 2}
        foreach coordinate $point {if {![string is integer -strict $coordinate] || abs($coordinate)>1000000} {exit 2}}
    }
}
set changeHotSpot 0;set changeVisible 0
if {[dict exists $spec changeHotSpot]} {
    foreach key {changeHotSpot newHotSpot changeVisible newVisible expectedHotSpot expectedVisible} {set $key [dict get $spec $key]}
    foreach flag [list $changeHotSpot $changeVisible $newVisible $expectedVisible] {if {![string is boolean -strict $flag]} {exit 2}}
    foreach point [list $newHotSpot $expectedHotSpot] {
        if {[llength $point]!=2} {exit 2}
        foreach coordinate $point {if {![string is integer -strict $coordinate] || abs($coordinate)>1000000} {exit 2}}
    }
}
set identity [dict get $spec identity]
lassign [list {*}[lmap key {packageName deviceDesignator cellName partName devicePosition} {dict get $identity $key}]] expectedPackage expectedDesignator expectedCell expectedPart expectedDevicePosition
foreach flag [list $changeName $changeNumber $changeType] {if {![string is boolean -strict $flag]} {exit 2}}
set selectedCount 0
set selected {};set phase opening
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set lib [$session GetLibAndSchematics [cmcp::cs $source] $state]; cmcp::check $state
    if {$lib eq "NULL"} {error "no_library"}
    set packages {}; set devices {}; set cells {}; set parts {}; set pins {}
    set iterator [$lib NewPackagesIter $state]; cmcp::check $state
    try {
        set packageIndex 0
        for {set pkg [$iterator NextPackage $state]} {$pkg ne "NULL"} {set pkg [$iterator NextPackage $state]} {
            cmcp::check $state; cmcp::tick
            set packageId "package-[incr packageIndex]"
            set name [cmcp::cs ""]; cmcp::check [$pkg GetName $name]
            set size [$pkg GetSize $state]; cmcp::check $state
            set homogeneous [$pkg IsHomogeneous $state]; cmcp::check $state
            set footprint [cmcp::cs ""]; cmcp::check [$pkg GetPCBFootprint $footprint]
            lappend packages [cmcp::obj objectId [cmcp::q $packageId] name [cmcp::q [cmcp::str $name]] size $size homogeneous [expr {$homogeneous ? "true" : "false"}] footprint [cmcp::q [cmcp::str $footprint]]]
            set di [$pkg NewDevicesIter $state]; cmcp::check $state
            try {
                set deviceIndex 0
                for {set device [$di NextDevice $state]} {$device ne "NULL"} {set device [$di NextDevice $state]} {
                    cmcp::check $state; cmcp::tick
                    set deviceId "$packageId/device-[incr deviceIndex]"
                    set designator [cmcp::cs ""]; cmcp::check [$device GetDesignator $designator]
                    set position [$device GetPosition $state]; cmcp::check $state
                    set cell [$device GetCell $state]; cmcp::check $state
                    if {$cell eq "NULL"} {error "missing_cell"}
                    set cellId "$deviceId/cell"
                    set cellName [cmcp::cs ""]; cmcp::check [$device GetCellName $cellName]
                    cmcp::tick
                    lappend devices [cmcp::obj objectId [cmcp::q $deviceId] packageId [cmcp::q $packageId] designator [cmcp::q [cmcp::str $designator]] position $position cellId [cmcp::q $cellId]]
                    lappend cells [cmcp::obj objectId [cmcp::q $cellId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $cellName]]]
                    set pi [$cell NewPartsIter $state]; cmcp::check $state
                    try {
                        set partIndex 0
                        for {set part [$pi NextPart $state]} {$part ne "NULL"} {set part [$pi NextPart $state]} {
                            cmcp::check $state; cmcp::tick
                            set partId "$cellId/part-[incr partIndex]"
                            set partName [cmcp::cs ""]; cmcp::check [$part GetName $partName]
                            lappend parts [cmcp::obj objectId [cmcp::q $partId] cellId [cmcp::q $cellId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $partName]]]
                            set pinsIter [$part NewLPinsIter $state]; cmcp::check $state
                            try {
                                set pinIndex 0
                                for {set pin [$pinsIter NextPin $state]} {$pin ne "NULL"} {set pin [$pinsIter NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    set pinId "$partId/pin-[incr pinIndex]"
                                    set pinName [cmcp::cs ""]; cmcp::check [$pin GetPinName $pinName]
                                    set logicalPosition [$pin GetPinPosition $state]; cmcp::check $state
                                    set number [cmcp::cs ""]; cmcp::check [$device GetPinNumber $logicalPosition $number]
                                    set pinType [$pin GetPinType $state]; cmcp::check $state
                                    set visible [$pin GetIsVisible $state]; cmcp::check $state
                                    set shared [$device GetIsShared $logicalPosition $state]; cmcp::check $state
                                    set swapId [$device GetPinSwapId $logicalPosition $state]; cmcp::check $state
                                    set hotSpot [$pin GetHotSpot $state]; cmcp::check $state
                                    lappend pins [cmcp::obj objectId [cmcp::q $pinId] partId [cmcp::q $partId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $pinName]] position $logicalPosition number [cmcp::q [cmcp::str $number]] pinType $pinType visible [expr {$visible ? "true" : "false"}] shared [expr {$shared ? "true" : "false"}] swapId $swapId hotSpot [cmcp::point $hotSpot]]
                                    if {[cmcp::str $name] eq $expectedPackage && [cmcp::str $designator] eq $expectedDesignator && $position==$expectedDevicePosition && [cmcp::str $cellName] eq $expectedCell && [cmcp::str $partName] eq $expectedPart && $logicalPosition==$expectedPosition} {
                                        incr selectedCount
                                        set phase checking_target
                                        if {[cmcp::str $name] ne $expectedPackage || [cmcp::str $designator] ne $expectedDesignator || [cmcp::str $cellName] ne $expectedCell || [cmcp::str $partName] ne $expectedPart} {error target_identity_changed}
                                        if {[cmcp::str $pinName] ne $expectedName || [cmcp::str $number] ne $expectedNumber || $pinType != $expectedType || $logicalPosition != $expectedPosition} {error old_pin_mismatch}
                                        if {$changeHotSpot || $changeVisible} {
                                            set actualHotSpot [list [DboTclHelper_sGetCPointX $hotSpot] [DboTclHelper_sGetCPointY $hotSpot]]
                                            if {$actualHotSpot ne $expectedHotSpot || !!$visible != !!$expectedVisible} {error old_pin_geometry_mismatch}
                                        }
                                        if {$changeStartPoint} {
                                            set start [$pin GetStartPoint $state];cmcp::check $state
                                            if {[list [DboTclHelper_sGetCPointX $start] [DboTclHelper_sGetCPointY $start]] ne $expectedStartPoint} {error old_pin_start_mismatch}
                                        }
                                        set selected [list $pin $device]
                                    }
                                }
                            } finally {delete_DboLibPartPinsIter $pinsIter}
                        }
                    } finally {delete_DboCellPartsIter $pi}
                }
            } finally {delete_DboPackageDevicesIter $di}
        }
    } finally {delete_DboLibPackagesIter $iterator}
    if {$selectedCount != 1 || [llength $selected] != 2} {error pin_not_found}
    lassign $selected pin device
    if {[dict exists $spec pinStyle]} {
        set phase check_pin_style;set actualStyle [cmcp::pinStyle $pin]
        dict for {key value} [dict get $spec expectedStyle] {if {[dict get $actualStyle $key]!=[expr {$value ? 1 : 0}]} {error old_pin_style_mismatch}}
        foreach {key setter} {long SetIsLong clock SetIsClock dot SetIsDot} {
            if {[dict exists $spec pinStyle $key]} {set phase set_pin_style;cmcp::check [$pin $setter [expr {[dict get $spec pinStyle $key] ? 1 : 0}]]}
        }
    }
    if {$changeName} {set phase set_pin_name;cmcp::check [$pin SetPinName [cmcp::cs $newName]]}
    if {$changeType} {set phase set_pin_type;cmcp::check [$pin SetPinType $newType]}
    if {$changeNumber} {set phase set_device_number;cmcp::check [$device SetPinNumber $expectedPosition [cmcp::cs $newNumber]]}
    if {$changeStartPoint} {set phase set_start_point;cmcp::check [$pin SetStartPoint [DboTclHelper_sMakeCPoint {*}$newStartPoint]]}
    if {$changeHotSpot} {set phase set_hotspot;cmcp::check [$pin SetHotSpot [DboTclHelper_sMakeCPoint {*}$newHotSpot]]}
    if {$changeVisible} {set phase set_visibility;cmcp::check [$pin SetIsVisible [expr {!!$newVisible}]]}
    set phase mark_library
    cmcp::check [$session MarkAllLibForSave $lib]
    set phase save_library
    cmcp::check [$session SaveLib $lib]
    set phase receipt
    set stream [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $stream -encoding utf-8 -translation lf;puts -nonewline $stream [cmcp::obj saved true pinId [cmcp::q $targetPin]]} finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    catch {
        set stream [open $output {WRONLY CREAT EXCL}]
        try {fconfigure $stream -encoding utf-8 -translation lf;puts -nonewline $stream [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} finally {close $stream}
    }
    exit 1
}
