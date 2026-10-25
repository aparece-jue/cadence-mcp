# Explicit bReturnShared=1: retain each unit shared-pin definition row.
# Read native placement and actual pin hotspots of one immutable definition ID. No mutation or GUI.
# argv: installRoot copiedDSN resultJSON partId maxObjects maxProperties
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_error"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
set count 0
proc cmcp::tick {} {
    global count maxObjects
    if {[incr count] > $maxObjects} {error "object_limit"}
}
if {$argc != 6} {exit 2}
lassign $argv root design output partId maxObjects maxProperties
if {![regexp {^schematic-[1-9][0-9]*/page-[1-9][0-9]*/part-[1-9][0-9]*$} $partId]} {exit 2}
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]; cmcp::check $state
    if {$d eq "NULL"} {error "no_design"}
    set found ""
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS]; cmcp::check $state
    try {
        set si 0
        for {set v [$vi NextView $state]} {$v ne "NULL" && $found eq ""} {set v [$vi NextView $state]} {
            cmcp::check $state; cmcp::tick
            set s [DboViewToDboSchematic $v]
            set sn [cmcp::cs ""]; $s GetName $sn
            set sid "schematic-[incr si]"
            set pi [$s NewPagesIter $state]; cmcp::check $state
            try {
                set pn 0
                for {set p [$pi NextPage $state]} {$p ne "NULL" && $found eq ""} {set p [$pi NextPage $state]} {
                    cmcp::check $state; cmcp::tick
                    set pageId "$sid/page-[incr pn]"
                    set pageName [cmcp::cs ""]; $p GetName $pageName
                    set it [$p NewPartInstsIter $state]; cmcp::check $state
                    try {
                        set oi 0
                        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
                            cmcp::check $state; cmcp::tick
                            if {"$pageId/part-[incr oi]" ne $partId} {continue}
                            set ref [cmcp::cs ""]; $part GetReference $ref
                            set location [$part GetLocation $state]; cmcp::check $state
                            set rotation [$part GetRotation $state]; cmcp::check $state
                            set mirror [$part GetMirror $state]; cmcp::check $state
                            set definition [$part GetDefiningPart [DboState]]
                            set boxes {}
                            foreach box [list [$part GetBoundingBox] [$part GetOffsetBoundingBox [DboState]] [$definition GetBoundingBox]] {
                              lappend boxes [cmcp::arr [list [cmcp::point [DboTclHelper_sGetCRectTopLeft $box]] [cmcp::point [DboTclHelper_sGetCRectBottomRight $box]]]]
                            }
                            set actualPins {}
                            set pinIterator [$part NewPinsIter $state $::IterDefs_ALL 1]; cmcp::check $state
                            try {
                                set pinIndex 0
                                for {set pin [$pinIterator NextPin $state]} {$pin ne "NULL"} {set pin [$pinIterator NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    if {[llength $actualPins] >= $maxProperties} {error "pin_limit"}
                                    set number [cmcp::cs ""]; $pin GetPinNumber $number
                                    set name [cmcp::cs ""]; $pin GetPinName $name
                                    set hotSpot [$pin GetOffsetHotSpot $state]; cmcp::check $state
                                    set local [[$pin GetDefiningPin [DboState]] GetHotSpot [DboState]]
                                    set converted [$part GetOffsetGraphicPoint $local]
                                    lappend actualPins [cmcp::obj pinId [cmcp::q "$partId/pin-[incr pinIndex]"] number [cmcp::q [cmcp::str $number]] name [cmcp::q [cmcp::str $name]] hotSpot [cmcp::point $hotSpot] localHotSpot [cmcp::point $local] converted [cmcp::point $converted]]
                                }
                            } finally {delete_DboPartInstPinsIter $pinIterator}
                            set found [cmcp::obj boxes [cmcp::arr $boxes] partId [cmcp::q $partId] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $ref]] location [cmcp::point $location] rotationCode $rotation mirrorCode $mirror pins [cmcp::arr $actualPins]]
                            break
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {$found eq ""} {error "object_not_found"}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {
        fconfigure $stream -encoding utf-8 -translation lf
        puts -nonewline $stream $found
    } finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: part geometry inspection failed"; exit 1}
