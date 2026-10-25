# Owned pose fixture only: do not use on real designs. Defining-pin oracle precedes instance mutation.
# argv: installRoot copiedDSN oracleJSON partId maxObjects rotation mirror x y
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_error"}}
set count 0
proc cmcp::tick {} {
    global count maxObjects
    if {[incr count] > $maxObjects} {error "object_limit"}
}
if {$argc != 9} {exit 2}
lassign $argv root design output partId maxObjects rotation mirror x y
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
                            set localPins {}
                            set pit [$part NewPinsIter $state]; cmcp::check $state
                            try {
                                for {set pin [$pit NextPin $state]} {$pin ne "NULL"} {set pin [$pit NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    set number [cmcp::cs ""]; cmcp::check [$pin GetPinNumber $number]
                                    set name [cmcp::cs ""]; cmcp::check [$pin GetPinName $name]
                                    set defining [$pin GetDefiningPin $state]; cmcp::check $state
                                    if {$defining eq "NULL"} {error "missing_definition_pin"}
                                    set local [$defining GetHotSpot $state]; cmcp::check $state
                                    lappend localPins [cmcp::obj number [cmcp::q [cmcp::str $number]] name [cmcp::q [cmcp::str $name]] localHotSpot [cmcp::arr [list [DboTclHelper_sGetCPointX $local] [DboTclHelper_sGetCPointY $local]]]]
                                }
                            } finally {delete_DboPartInstPinsIter $pit}
                            # The independent oracle above comes from immutable
                            # symbol-definition pins, before changing the instance.
                            cmcp::check [$part SetMirror $mirror]
                            cmcp::check [$part SetRotation $rotation]
                            cmcp::check [$part SetLocation [DboTclHelper_sMakeCPoint $x $y]]
                            cmcp::check [$p MarkModified]
                            cmcp::check [$s MarkModified $p]
                            cmcp::check [$s SavePage $p]
                            cmcp::check [$d SaveSchematic $s]
                            cmcp::check [$session MarkAllLibForSave $d]
                            cmcp::check [$session SaveDesign $d]
                            set found [cmcp::obj partId [cmcp::q $partId] localPins [cmcp::arr $localPins] rotationCode $rotation mirrorCode $mirror location [cmcp::arr [list $x $y]]]

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
if {$rc} {puts stderr "CADENCE_DBO_ERROR: property inspection failed"; exit 1}
