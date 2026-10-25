# Read complete bounded design effective-property multiset. No mutation or GUI.
# argv: installRoot copiedDSN resultJSON maxObjects maxProperties
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_error"}}
set count 0
proc cmcp::tick {} {
    global count maxObjects
    if {[incr count] > $maxObjects} {error "object_limit"}
}
if {$argc != 5} {exit 2}
lassign $argv root design output maxObjects maxProperties
set propertyCount 0;set propertyBytes 0
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
            set sn [cmcp::cs ""]; cmcp::check [$s GetName $sn]
            set sid "schematic-[incr si]"
            set pi [$s NewPagesIter $state]; cmcp::check $state
            try {
                set pn 0
                for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
                    cmcp::check $state; cmcp::tick
                    set pageId "$sid/page-[incr pn]"
                    set pageName [cmcp::cs ""]; cmcp::check [$p GetName $pageName]
                    set it [$p NewPartInstsIter $state]; cmcp::check $state
                    try {
                        set oi 0
                        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
                            cmcp::check $state; cmcp::tick
                            if {[llength $found]>=1024} {error part_limit}
                            set partId "$pageId/part-[incr oi]"
                            set ref [cmcp::cs ""]; cmcp::check [$part GetReference $ref]
                            set properties {}
                            set props [$part NewEffectivePropsIter $state]; cmcp::check $state
                            try {
                                set name [cmcp::cs ""]; set value [cmcp::cs ""]
                                set valueType [DboTclHelper_sMakeDboValueType]
                                set editable [DboTclHelper_sMakeInt]
                                while {1} {
                                    set next [$props NextEffectiveProp $name $value $valueType $editable]
                                    if {[$next OK] != 1} {if {[$next Code]!=1022} {error "unexpected_property_iterator_end_[$next Code]"};break}
                                    if {[llength $properties] >= $maxProperties || [incr propertyCount]>16384} {error "property_limit"}
                                    set propertyNameText [cmcp::str $name];set propertyValueText [cmcp::str $value]
                                    if {[string length $propertyNameText]>256 || [string length $propertyValueText]>16384} {error property_text_limit}
                                    incr propertyBytes [string bytelength $propertyNameText];incr propertyBytes [string bytelength $propertyValueText]
                                    if {$propertyBytes>8388608} {error property_text_budget}
                                    lappend properties [cmcp::obj name [cmcp::q $propertyNameText] value [cmcp::q $propertyValueText]]
                                }
                            } finally {delete_DboEffectivePropsIter $props}
                            lappend found [cmcp::obj partId [cmcp::q $partId] schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $ref]] properties [cmcp::arr $properties]]
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
if {$rc} {puts stderr "CADENCE_DBO_ERROR: property inspection failed"; exit 1}
