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
if {$argc != 5} {exit 2}
lassign $argv root design output maxObjects maxProperties
set textBytes 0
proc cmcp::textBudget {name value} {
    global textBytes
    set n [cmcp::str $name];set v [cmcp::str $value]
    if {[string length $n]>256 || [string length $v]>16384} {error property_text_limit}
    incr textBytes [string bytelength $n];incr textBytes [string bytelength $v]
    if {$textBytes>8388608} {error property_text_budget}
}
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
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            cmcp::check $state; cmcp::tick
            set s [DboViewToDboSchematic $v]
            set sn [cmcp::cs ""]; $s GetName $sn
            set sid "schematic-[incr si]"
            set pi [$s NewPagesIter $state]; cmcp::check $state
            try {
                set pn 0
                for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
                    cmcp::check $state; cmcp::tick
                    set pageId "$sid/page-[incr pn]"
                    set pageName [cmcp::cs ""]; $p GetName $pageName
                    set it [$p NewPartInstsIter $state]; cmcp::check $state
                    try {
                        set oi 0
                        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
                            cmcp::check $state; cmcp::tick
                            if {[llength $found]>=128} {error instance_limit}
                            set partId "$pageId/part-[incr oi]"
                            set nativeId [$part GetId $state];cmcp::check $state
                            set partLocation [$part GetLocation $state];cmcp::check $state
                            set partRotation [$part GetRotation $state];cmcp::check $state
                            set partMirror [$part GetMirror $state];cmcp::check $state
                            set pinRows {};set pinIter [$part NewPinsIter $state $::IterDefs_ALL 1];cmcp::check $state
                            try {
                                for {set pin [$pinIter NextPin $state]} {$pin ne "NULL"} {set pin [$pinIter NextPin $state]} {
                                    cmcp::check $state;cmcp::tick
                                    if {[llength $pinRows]>=500} {error pin_limit}
                                    set pinNumber [cmcp::cs ""];set numberState [$pin GetPinNumber $pinNumber];set numberCode [$numberState Code]
                                    if {[$numberState Failed]} {
                                        if {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE || $numberCode!=1021 || [cmcp::str $pinNumber] ne ""} {cmcp::check $numberState}
                                    }
                                    set pinName [cmcp::cs ""];cmcp::check [$pin GetPinName $pinName]
                                    set pinHotSpot [$pin GetOffsetHotSpot $state];cmcp::check $state
                                    lappend pinRows [cmcp::obj numberState $numberCode number [cmcp::q [cmcp::str $pinNumber]] name [cmcp::q [cmcp::str $pinName]] hotSpot [cmcp::point $pinHotSpot]]
                                }
                            } finally {delete_DboPartInstPinsIter $pinIter}
                            if {[$state Failed] && [$state Code]!=1022} {error unexpected_pin_end}
                            set state [DboState]
                            set geometry [cmcp::obj physicalPinNumbersApplicable [expr {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE?"true":"false"}] location [cmcp::point $partLocation] rotationCode $partRotation mirrorCode $partMirror pins [cmcp::arr $pinRows]]
                            set ref [cmcp::cs ""]; $part GetReference $ref
                            set properties {}
                            set props [$part NewEffectivePropsIter $state]; cmcp::check $state
                            try {
                                set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                set valueType [DboTclHelper_sMakeDboValueType]
                                set editable [DboTclHelper_sMakeInt]
                                while {1} {
                                    set next [$props NextEffectiveProp $name $value $valueType $editable]
                                    if {[$next OK] != 1} {if {[$next Code]!=1022} {error unexpected_effective_end};break}
                                    if {[llength $properties] >= $maxProperties} {error "property_limit"}
                                    cmcp::textBudget $name $value
                                    lappend properties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
                                }
                            } finally {delete_DboEffectivePropsIter $props}
                            set userProperties {}
                            set state [DboState];set ui [$part NewUserPropsIter $state]; cmcp::check $state
                            try {
                                for {set prop [$ui NextUserProp $state]} {$prop ne "NULL"} {set prop [$ui NextUserProp $state]} {
                                    cmcp::check $state; cmcp::tick
                                    if {[llength $userProperties] >= $maxProperties} {error "property_limit"}
                                    set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                    cmcp::check [$prop GetName $name]
                                    cmcp::check [$prop GetStringValue $value]
                                    cmcp::textBudget $name $value
                                    set propType [$prop GetType $state];cmcp::check $state
                                    lappend userProperties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] nativeType $propType editable [$prop IsEditable] deletable [$prop IsDeletable]]
                                }
                            } finally {delete_DboUserPropsIter $ui}
                            if {[$state Failed] && [$state Code]!=1022} {error unexpected_user_end}
                            set displayProperties {}
                            set state [DboState];set di [$part NewDisplayPropsIter $state]; cmcp::check $state
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
                                    cmcp::textBudget $name $value
                                    lappend displayProperties [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] location [cmcp::point $location] rotationCode $rotation displayTypeCode $displayType colorCode $color]
                                }
                            } finally {delete_DboDisplayPropsIter $di}
                            if {[$state Failed] && [$state Code]!=1022} {error unexpected_display_end}
                            lappend found [cmcp::obj nativeId $nativeId partId [cmcp::q $partId] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $ref]] geometry $geometry effective [cmcp::arr $properties] user [cmcp::arr $userProperties] display [cmcp::arr $displayProperties]]
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {
        fconfigure $stream -encoding utf-8 -translation lf
        puts -nonewline $stream [cmcp::arr $found]
    } finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: property layers inspection failed"; exit 1}
