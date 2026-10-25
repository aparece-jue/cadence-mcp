# Official Dbo library object model; read-only isolated process.
# argv: installRoot copiedOLB outputJSON maxObjects
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_part_signature.tcl]
source [file join [file dirname [info script]] dbo_vector_json.tcl]
namespace eval cmcp {variable count 0; variable limit 100000}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error"}}
proc cmcp::tick {} {variable count; variable limit; if {[incr count] > $limit} {error "object_limit"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
if {$argc != 4 && $argc != 5} {exit 2}
set requireOrder 0
lassign $argv root source output cmcp::limit requireOrder
if {$requireOrder eq ""} {set requireOrder 0}
if {$requireOrder ni {0 1}} {exit 2}
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set lib [$session GetLibAndSchematics [cmcp::cs $source] $state]; cmcp::check $state
    if {$lib eq "NULL"} {error "no_library"}
    set packages {}; set devices {}; set cells {}; set parts {}; set pins {};set metaPackages {};set metaSymbols {}
    set iterator [$lib NewPackagesIter $state]; cmcp::check $state
    try {
        set packageIndex 0
        for {set pkg [$iterator NextPackage $state]} {$pkg ne "NULL"} {set pkg [$iterator NextPackage $state]} {
            cmcp::check $state; cmcp::tick
            set packageId "package-[incr packageIndex]"
            set name [cmcp::cs ""]; cmcp::check [$pkg GetName $name]
            set template [cmcp::cs ""];cmcp::check [$pkg GetReferenceTemplate $template]
            lappend metaPackages [cmcp::obj packageName [cmcp::q [cmcp::str $name]] referenceTemplate [cmcp::q [cmcp::str $template]]]
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
                            set vectorState [DboState]
                            set lines {};set otherTypes {};set pinStarts {};set orderedVectors {};set hasComplex 0
                            set vectors [$part NewVectorsIter $vectorState $::IterDefs_ALL];cmcp::check $vectorState
                            try {
                                for {set vector [$vectors NextVector $vectorState]} {$vector ne "NULL"} {set vector [$vectors NextVector $vectorState]} {
                                    cmcp::check $vectorState;cmcp::tick
                                    set type [$vector GetObjectType]
                                    if {$type ni [list $::DboBaseObject_LINE $::DboBaseObject_BOX $::DboBaseObject_ARC $::DboBaseObject_ELLIPSE $::DboBaseObject_POLYGON $::DboBaseObject_POLYLINE $::DboBaseObject_COMMENT_TEXT $::DboBaseObject_FILL $::DboBaseObject_BEZIER $::DboBaseObject_BITMAP_VECT]} {lappend otherTypes $type;continue}
                                    lappend orderedVectors [cmcp::descriptorJson [cmcp::vectorDescriptor $vector]]
                                    if {$type!=$::DboBaseObject_LINE} {set hasComplex 1;continue}
                                    set line [DboVectorToDboLine $vector]
                                    set start [$line GetStart $vectorState];cmcp::check $vectorState
                                    set end [$line GetEnd $vectorState];cmcp::check $vectorState
                                    set style [$line GetLineStyle $vectorState];cmcp::check $vectorState
                                    set width [$line GetLineWidth $vectorState];cmcp::check $vectorState
                                    lappend lines [cmcp::obj start [cmcp::point $start] end [cmcp::point $end] style $style width $width]
                                }
                            } finally {delete_DboGraphicObjectVectorsIter $vectors}
                            if {[$vectorState Failed] && [$vectorState Code]!=1022} {error unexpected_vector_iterator_end}
                            set pinsIter [$part NewLPinsIter $state]; cmcp::check $state
                            try {
                                set pinIndex 0
                                for {set pin [$pinsIter NextPin $state]} {$pin ne "NULL"} {set pin [$pinsIter NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    set pinId "$partId/pin-[incr pinIndex]"
                                    set pinName [cmcp::cs ""]; cmcp::check [$pin GetPinName $pinName]
                                    set logicalPosition [$pin GetPinPosition $state]; cmcp::check $state
                                    set start [$pin GetStartPoint $state];cmcp::check $state
                                    lappend pinStarts [cmcp::obj position $logicalPosition start [cmcp::point $start]]
                                    set number [cmcp::cs ""]; cmcp::check [$device GetPinNumber $logicalPosition $number]
                                    set pinType [$pin GetPinType $state]; cmcp::check $state
                                    set visible [$pin GetIsVisible $state]; cmcp::check $state
                                    set shared [$device GetIsShared $logicalPosition $state]; cmcp::check $state
                                    set swapId [$device GetPinSwapId $logicalPosition $state]; cmcp::check $state
                                    set hotSpot [$pin GetHotSpot $state]; cmcp::check $state
                                    lappend pins [cmcp::obj objectId [cmcp::q $pinId] partId [cmcp::q $partId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $pinName]] position $logicalPosition number [cmcp::q [cmcp::str $number]] pinType $pinType visible [expr {$visible ? "true" : "false"}] shared [expr {$shared ? "true" : "false"}] swapId $swapId hotSpot [cmcp::point $hotSpot]]
                                }
                            } finally {delete_DboLibPartPinsIter $pinsIter}
                            set scope [cmcp::arr [list [cmcp::q [cmcp::str $name]] [cmcp::q [cmcp::str $designator]] $position [cmcp::q [cmcp::str $cellName]] [cmcp::q [cmcp::str $partName]]]]
                            set metaArgs [list scope $scope pinStarts [cmcp::arr $pinStarts] lines [cmcp::arr $lines] otherVectorTypes [cmcp::arr $otherTypes]]
                            if {$requireOrder || $hasComplex} {lappend metaArgs orderedVectors [cmcp::arr $orderedVectors]}
                            lappend metaSymbols [cmcp::obj {*}$metaArgs]
                        }
                    } finally {delete_DboCellPartsIter $pi}
                }
            } finally {delete_DboPackageDevicesIter $di}
        }
    } finally {delete_DboLibPackagesIter $iterator}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {
        fconfigure $stream -encoding utf-8 -translation lf
        puts -nonewline $stream [cmcp::obj package [cmcp::arr $packages] device [cmcp::arr $devices] cell [cmcp::arr $cells] part [cmcp::arr $parts] pin [cmcp::arr $pins] meta [cmcp::obj packages [cmcp::arr $metaPackages] symbols [cmcp::arr $metaSymbols]]]
    } finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: library inspection failed: $message"; exit 1}
