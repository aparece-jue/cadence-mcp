# Explicit shared rows keep NC ownership aligned with definition pin IDs.
# Fixed connection/graphic inventories on a copied DSN. No mutation or GUI.
# argv: installRoot copiedDSN outputJSON mode
source [file join [file dirname [info script]] json.tcl]
namespace eval cmcp {variable count 0; variable objects {}}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error"}}
proc cmcp::tick {} {variable count; if {[incr count] > 100000} {error "object_limit"}}
proc cmcp::pt {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
proc cmcp::rect {r} {
    set a [DboTclHelper_sGetCRectTopLeft $r]; set b [DboTclHelper_sGetCRectBottomRight $r]
    return [cmcp::arr [list [DboTclHelper_sGetCPointX $a] [DboTclHelper_sGetCPointY $a] [DboTclHelper_sGetCPointX $b] [DboTclHelper_sGetCPointY $b]]]
}
proc cmcp::emit {kind object id page attributes} {
    variable objects
    cmcp::tick
    set state [DboState]; set native [$object GetId $state]; cmcp::check $state
    lappend objects [cmcp::obj kind [cmcp::q $kind] objectId [cmcp::q $id] pageId [cmcp::q $page] nativeId $native objectType [$object GetObjectType] attributes $attributes]
}
proc cmcp::properties {object} {
    set state [DboState]; set result {}
    set it [$object NewEffectivePropsIter $state]; cmcp::check $state
    try {
        set name [cmcp::cs ""]; set value [cmcp::cs ""]
        set t [DboTclHelper_sMakeDboValueType]; set edit [DboTclHelper_sMakeInt]
        while {1} {
            set next [$it NextEffectiveProp $name $value $t $edit]
            if {[$next OK] != 1} {break}
            cmcp::tick
            if {[llength $result] >= 512} {error "property_limit"}
            lappend result [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
        }
    } finally {delete_DboEffectivePropsIter $it}
    return [cmcp::arr $result]
}
proc cmcp::graphic {object} {
    set state [DboState]
    set name [cmcp::cs ""]; cmcp::check [$object GetName $name]
    set location [$object GetLocation $state]; cmcp::check $state
    set rotation [$object GetRotation $state]; cmcp::check $state
    set mirror [$object GetMirror $state]; cmcp::check $state
    return [list name [cmcp::q [cmcp::str $name]] location [cmcp::pt $location] rotationCode $rotation mirrorCode $mirror bounds [cmcp::rect [$object GetBoundingBox]]]
}
proc cmcp::connections {page pageId} {
    set state [DboState]
    set it [$page NewWiresIter $state]; cmcp::check $state
    try {
        set n 0
        for {set wire [$it NextWire $state]} {$wire ne "NULL"} {set wire [$it NextWire $state]} {
            cmcp::check $state; set id "$pageId/wire-[incr n]"
            set count [$wire GetPointCount $state]; cmcp::check $state
            if {$count < 2 || $count > 10000} {error "point_limit"}
            set points {}
            for {set i 0} {$i < $count} {incr i} {
                cmcp::tick; set point [$wire GetPoint $i $state]; cmcp::check $state
                lappend points [cmcp::pt $point]
            }
            set net [cmcp::cs ""]; cmcp::check [$wire GetNetName $net]
            cmcp::emit wire $wire $id $pageId [cmcp::obj net [cmcp::q [cmcp::str $net]] points [cmcp::arr $points]]
            set aliases [$wire NewAliasesIter $state]; cmcp::check $state
            try {
                set an 0
                for {set alias [$aliases NextAlias $state]} {$alias ne "NULL"} {set alias [$aliases NextAlias $state]} {
                    cmcp::check $state
                    set name [cmcp::cs ""]; cmcp::check [$alias GetName $name]
                    set location [$alias GetLocation $state]; cmcp::check $state
                    cmcp::emit alias $alias "$id/alias-[incr an]" $pageId [cmcp::obj wireId [cmcp::q $id] name [cmcp::q [cmcp::str $name]] location [cmcp::pt $location]]
                }
            } finally {delete_DboWireAliasesIter $aliases}
        }
    } finally {delete_DboPageWiresIter $it}
    # All method names below are fixed internal constants, never client input.
    foreach {kind make next remove} {
        global NewGlobalsIter NextGlobal delete_DboPageGlobalsIter
        port NewPortsIter NextPort delete_DboPagePortsIter
        offpage NewOffPageConnectorsIter NextOffPageConnector delete_DboPageOffPageConnectorsIter
    } {
        if {$kind eq "global"} {set it [$page $make $state]} else {set it [$page $make $state $::IterDefs_ALL]}
        cmcp::check $state
        try {
            set n 0
            for {set object [$it $next $state]} {$object ne "NULL"} {set object [$it $next $state]} {
                cmcp::check $state
                set name [cmcp::cs ""]; cmcp::check [$object GetName $name]
                set symbol [cmcp::cs ""]; cmcp::check [$object GetSourceSymbolName $symbol]
                set location [$object GetLocation $state]; cmcp::check $state
                set hotSpot [$object GetOffsetHotSpot $state]; cmcp::check $state
                set rotation [$object GetRotation $state]; cmcp::check $state
                set mirror [$object GetMirror $state]; cmcp::check $state
                set bus [$object IsBus $state]; cmcp::check $state
                cmcp::emit $kind $object "$pageId/$kind-[incr n]" $pageId [cmcp::obj name [cmcp::q [cmcp::str $name]] sourceSymbol [cmcp::q [cmcp::str $symbol]] location [cmcp::pt $location] hotSpot [cmcp::pt $hotSpot] rotationCode $rotation mirrorCode $mirror isBus [expr {$bus ? "true" : "false"}]]
            }
        } finally {$remove $it}
    }
}
proc cmcp::parts {page pageId mode} {
    set state [DboState]
    set it [$page NewPartInstsIter $state]; cmcp::check $state
    try {
        set n 0
        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
            cmcp::check $state; cmcp::tick; set id "$pageId/part-[incr n]"
            set ref [cmcp::cs ""]; cmcp::check [$part GetReference $ref]
            if {$mode eq "connections"} {
                set pi [$part NewPinsIter $state $::IterDefs_ALL 1]; cmcp::check $state
                try {
                    set ni 0
                    for {set pin [$pi NextPin $state]} {$pin ne "NULL"} {set pin [$pi NextPin $state]} {
                        cmcp::check $state; cmcp::tick; incr ni
                        set nc [$pin GetIsNoConnect $state]; cmcp::check $state
                        if {!$nc} {continue}
                        set number [cmcp::cs ""]; cmcp::check [$pin GetPinNumber $number]
                        set hotSpot [$pin GetOffsetHotSpot $state]; cmcp::check $state
                        cmcp::emit nc $pin "$id/pin-$ni/nc" $pageId [cmcp::obj partId [cmcp::q $id] pinId [cmcp::q "$id/pin-$ni"] reference [cmcp::q [cmcp::str $ref]] number [cmcp::q [cmcp::str $number]] hotSpot [cmcp::pt $hotSpot]]
                    }
                } finally {delete_DboPartInstPinsIter $pi}
            } else {
                set attributes [cmcp::graphic $part]
                # Part reference is separate from its graphic/symbol name.
                cmcp::emit part_bounds $part "$id/bounds" $pageId [cmcp::obj {*}$attributes partId [cmcp::q $id] reference [cmcp::q [cmcp::str $ref]]]
                set di [$part NewDisplayPropsIter $state]; cmcp::check $state
                try {
                    set dn 0
                    for {set dp [$di NextProp $state]} {$dp ne "NULL"} {set dp [$di NextProp $state]} {
                        cmcp::check $state
                        set name [cmcp::cs ""]; set value [cmcp::cs ""]
                        cmcp::check [$dp GetName $name]; cmcp::check [$dp GetValueString $value]
                        set location [$dp GetLocation $state]; cmcp::check $state
                        set rotation [$dp GetRotation $state]; cmcp::check $state
                        set display [$dp GetDisplayType $state]; cmcp::check $state
                        set color [$dp GetColor $state]; cmcp::check $state
                        cmcp::emit display_property $dp "$id/display-[incr dn]" $pageId [cmcp::obj partId [cmcp::q $id] name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] location [cmcp::pt $location] rotationCode $rotation displayTypeCode $display colorCode $color bounds [cmcp::rect [$dp GetBoundingBox]] boundsDirty [expr {[$dp IsBoundingBoxDirty] ? "true" : "false"}]]
                    }
                } finally {delete_DboDisplayPropsIter $di}
            }
        }
    } finally {delete_DboPagePartInstsIter $it}
}
proc cmcp::graphics {page pageId} {
    set state [DboState]
    foreach {kind make next remove} {
        graphic NewCommentGraphicsIter NextCommentGraphic delete_DboPageCommentGraphicsIter
        titleblock NewTitleBlocksIter NextTitleBlock delete_DboPageTitleBlocksIter
    } {
        set it [$page $make $state]; cmcp::check $state
        try {
            set n 0
            for {set object [$it $next $state]} {$object ne "NULL"} {set object [$it $next $state]} {
                cmcp::check $state
                set attrs [cmcp::graphic $object]
                set text null
                if {$kind eq "graphic" && [$object GetObjectType] == $::DboBaseObject_GRAPHIC_COMMENTTEXT_INST} {
                    set comment [DboGraphicInstanceToDboGraphicCommentTextInst $object]
                    set native [$comment GetDboCommentText]
                    set value [cmcp::cs ""]; cmcp::check [$native GetText $value]
                    set text [cmcp::q [cmcp::str $value]]
                }
                if {$kind eq "titleblock"} {lappend attrs properties [cmcp::properties $object]}
                cmcp::emit $kind $object "$pageId/$kind-[incr n]" $pageId [cmcp::obj {*}$attrs text $text]
            }
        } finally {$remove $it}
    }
}
if {$argc != 4} {exit 2}
lassign $argv root design output mode
if {$mode ni {connections graphics}} {exit 2}
set session ""; set phase opening
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]; set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]; cmcp::check $state
    if {$d eq "NULL"} {error "no_design"}
    set schematics {}; set pages {}
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS]; cmcp::check $state
    try {
        set si 0
        for {set view [$vi NextView $state]} {$view ne "NULL"} {set view [$vi NextView $state]} {
            cmcp::check $state; cmcp::tick; set schematic [DboViewToDboSchematic $view]
            set name [cmcp::cs ""]; cmcp::check [$schematic GetName $name]
            set sid "schematic-[incr si]"
            lappend schematics [cmcp::obj objectId [cmcp::q $sid] name [cmcp::q [cmcp::str $name]]]
            set pi [$schematic NewPagesIter $state]; cmcp::check $state
            try {
                set pn 0
                for {set page [$pi NextPage $state]} {$page ne "NULL"} {set page [$pi NextPage $state]} {
                    cmcp::check $state; cmcp::tick; set pageId "$sid/page-[incr pn]"
                    set name [cmcp::cs ""]; cmcp::check [$page GetName $name]
                    lappend pages [cmcp::obj objectId [cmcp::q $pageId] schematicId [cmcp::q $sid] name [cmcp::q [cmcp::str $name]]]
                    set phase "parts_$mode"; cmcp::parts $page $pageId $mode
                    set phase $mode
                    if {$mode eq "connections"} {cmcp::connections $page $pageId} else {cmcp::graphics $page $pageId}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $stream -encoding utf-8 -translation lf; puts -nonewline $stream [cmcp::obj schematic [cmcp::arr $schematics] page [cmcp::arr $pages] objects [cmcp::arr $cmcp::objects]]} finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: page inventory phase=$phase error=$message"; exit 1}
