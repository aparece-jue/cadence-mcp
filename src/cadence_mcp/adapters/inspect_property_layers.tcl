# Read effective properties of one immutable definition ID. No mutation or GUI.
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
                            set properties {}
                            set props [$part NewEffectivePropsIter $state]; cmcp::check $state
                            try {
                                set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                set valueType [DboTclHelper_sMakeDboValueType]
                                set editable [DboTclHelper_sMakeInt]
                                while {1} {
                                    set next [$props NextEffectiveProp $name $value $valueType $editable]
                                    if {[$next OK] != 1} {break}
                                    if {[llength $properties] >= $maxProperties} {error "property_limit"}
                                    lappend properties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
                                }
                            } finally {delete_DboEffectivePropsIter $props}
                            set userProperties {}
                            set ui [$part NewUserPropsIter $state]; cmcp::check $state
                            try {
                                for {set prop [$ui NextUserProp $state]} {$prop ne "NULL"} {set prop [$ui NextUserProp $state]} {
                                    cmcp::check $state; cmcp::tick
                                    if {[llength $userProperties] >= $maxProperties} {error "property_limit"}
                                    set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                    cmcp::check [$prop GetName $name]
                                    cmcp::check [$prop GetStringValue $value]
                                    lappend userProperties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
                                }
                            } finally {delete_DboUserPropsIter $ui}
                            set displayProperties {}
                            set di [$part NewDisplayPropsIter $state]; cmcp::check $state
                            try {
                                for {set prop [$di NextProp $state]} {$prop ne "NULL"} {set prop [$di NextProp $state]} {
                                    cmcp::check $state; cmcp::tick
                                    if {[llength $displayProperties] >= $maxProperties} {error "property_limit"}
                                    set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                    cmcp::check [$prop GetName $name]
                                    cmcp::check [$prop GetValueString $value]
                                    set location [$prop GetLocation $state]; cmcp::check $state
                                    set rotation [$prop GetRotation $state]; cmcp::check $state
                                    set displayType [$prop GetDisplayType $state]; cmcp::check $state
                                    set color [$prop GetColor $state]; cmcp::check $state
                                    lappend displayProperties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] location [cmcp::point $location] rotationCode $rotation displayTypeCode $displayType colorCode $color]
                                }
                            } finally {delete_DboDisplayPropsIter $di}
                            set found [cmcp::obj partId [cmcp::q $partId] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $ref]] effective [cmcp::arr $properties] user [cmcp::arr $userProperties] display [cmcp::arr $displayProperties]]
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
if {$rc} {puts stderr "CADENCE_DBO_ERROR: property layers inspection failed"; exit 1}
