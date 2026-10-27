# Explicit bReturnShared=1: retain each unit shared-pin definition row.
# Read native placement and actual pin hotspots of one immutable definition ID. No mutation or GUI.
# argv: installRoot copiedDSN resultJSON partId maxObjects maxProperties
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
source [file join [file dirname [info script]] dbo_vector_json.tcl]
proc cmcp::corners {r} {lassign $r x1 y1 x2 y2;list [list $x1 $y1] [list $x2 $y1] [list $x2 $y2] [list $x1 $y2]}
proc cmcp::controlPoints {v} {
 switch -- [lindex $v 0] {
  line {return [list [lindex $v 1] [lindex $v 2]]}
  box - ellipse {return [cmcp::corners [lindex $v 1]]}
  arc {return [concat [cmcp::corners [lindex $v 1]] [list [lindex $v 2] [lindex $v 3]]]}
  polygon - polyline - bezier {return [lindex $v 1]}
  text {return [concat [list [lindex $v 2]] [cmcp::corners [lindex $v 3]]]}
  bitmap {return [concat [list [lindex $v 2]] [cmcp::corners [lindex $v 1]]]}
  default {error unsupported_control_points}
 }
}
proc cmcp::shapePoint {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}
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
                            set ds [DboState];set definition [$part GetDefiningPart $ds];cmcp::check $ds
                            if {$definition eq "NULL"} {error missing_part_definition}
                            set boxes {}
                            foreach box [list [$part GetBoundingBox] [$part GetOffsetBoundingBox [DboState]] [$definition GetBoundingBox]] {
                              lappend boxes [cmcp::arr [list [cmcp::point [DboTclHelper_sGetCRectTopLeft $box]] [cmcp::point [DboTclHelper_sGetCRectBottomRight $box]]]]
                            }
                            set vectorRows {};set vectorCount 0;set pointCount 0;set textCount 0
                            set vs [DboState];set vectors [$definition NewVectorsIter $vs $::IterDefs_ALL];if {[$vs Failed]} {error "create_vectors_[$vs Code]"}
                            try {
                              for {set vector [$vectors NextVector $vs]} {$vector ne "NULL"} {set vector [$vectors NextVector $vs]} {
                                cmcp::check $vs;cmcp::tick
                                if {[incr vectorCount]>4096} {error vector_limit}
                                set type [$vector GetObjectType];set id null
                                set value {};set descriptor null;set points {};set kind unsupported;set supported 0
                                foreach constant {LINE BOX ELLIPSE ARC POLYGON POLYLINE BEZIER COMMENT_TEXT BITMAP_VECT} {
                                  if {[info exists ::DboBaseObject_$constant] && $type==[set ::DboBaseObject_$constant]} {set supported 1;break}
                                }
                                if {$supported} {
                                  set value [cmcp::vectorDescriptor $vector];set kind [lindex $value 0];set descriptor [cmcp::descriptorJson $value]
                                  set localPoints [cmcp::controlPoints $value];incr pointCount [llength $localPoints]
                                  if {$pointCount>65536} {error point_budget}
                                  if {$kind eq "text"} {incr textCount [string length [lindex $value 1]];if {$textCount>262144} {error text_budget}}
                                  foreach xy $localPoints {lappend points [cmcp::point [$part GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}$xy]]]}
                                }
                                lappend vectorRows [cmcp::obj index [expr {$vectorCount-1}] nativeId $id nativeTypeCode $type kind [cmcp::q $kind] location [cmcp::point $location] rotationCode $rotation mirrorCode $mirror localDescriptor $descriptor pageControlPoints [cmcp::arr $points]]
                              }
                            } finally {delete_DboGraphicObjectVectorsIter $vectors}
                            if {[$vs Failed] && [$vs Code]!=1022} {error unexpected_vector_iterator_end}
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
                            set found [cmcp::obj vectors [cmcp::arr $vectorRows] boxes [cmcp::arr $boxes] partId [cmcp::q $partId] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $ref]] location [cmcp::point $location] rotationCode $rotation mirrorCode $mirror pins [cmcp::arr $actualPins]]
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
if {$rc} {puts stderr $::errorInfo}
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: part vector inspection failed: $message"; exit 1}
