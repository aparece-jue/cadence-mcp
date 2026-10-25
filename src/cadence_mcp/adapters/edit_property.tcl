# Fixed Value/PCB Footprint mutation on a new isolated output copy only.
# argv: installRoot copiedDSN resultJSON partId maxObjects maxProperties
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_error"}}
set count 0
proc cmcp::tick {} {
    global count maxObjects
    if {[incr count] > $maxObjects} {error "object_limit"}
}
if {$argc != 11} {exit 2}
lassign $argv root design output partId maxObjects propertyName oldValue newValue expectedSchematic expectedPage expectedReference
if {$propertyName ni {Value {PCB Footprint} Implementation TC1 TC2}} {exit 2}
set phase opening
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
                            set phase checking_identity
                            if {[cmcp::str $sn] ne $expectedSchematic || [cmcp::str $pageName] ne $expectedPage || [cmcp::str $ref] ne $expectedReference} {error "identity_mismatch"}
                            set current [cmcp::cs ""]
                            cmcp::check [$part GetEffectivePropStringValue [cmcp::cs $propertyName] $current]
                            if {[cmcp::str $current] ne $oldValue} {error "old_value_mismatch"}
                            if {$propertyName eq "Implementation"} {
                                set implementationType [cmcp::cs ""]
                                cmcp::check [$part GetEffectivePropStringValue [cmcp::cs {Implementation Type}] $implementationType]
                                if {[cmcp::str $implementationType] ne "PSpice Model"} {error model_type_required}
                            }
                            set phase setting_property
                            cmcp::check [$part SetEffectivePropStringValue [cmcp::cs $propertyName] [cmcp::cs $newValue]]
                            set phase marking_page
                            cmcp::check [$p MarkModified]
                            cmcp::check [$s MarkModified $p]
                            set phase saving_page
                            cmcp::check [$s SavePage $p]
                            set phase saving_schematic
                            cmcp::check [$d SaveSchematic $s]
                            set phase saving_design
                            cmcp::check [$session MarkAllLibForSave $d]
                            cmcp::check [$session SaveDesign $d]
                            set phase saved
                            set found [cmcp::obj saved true partId [cmcp::q $partId] property [cmcp::q $propertyName]]
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
if {$rc} {
    catch {
        set stream [open $output {WRONLY CREAT EXCL}]
        try {fconfigure $stream -encoding utf-8 -translation lf; puts -nonewline $stream [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]} finally {close $stream}
    }
    puts stderr "CADENCE_DBO_ERROR: fixed property edit failed"; exit 1
}
