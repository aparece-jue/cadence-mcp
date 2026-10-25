# Self-authored fixed metadata-property access shared by bridge and verifier.
namespace eval ::cmcpProperty {}
proc ::cmcpProperty::cs {text} {return [DboTclHelper_sMakeCString $text]}
proc ::cmcpProperty::check {status} {if {[$status Failed]} {error "dbo_error"}}
proc ::cmcpProperty::find {design schematicName pageName reference} {
    set state [DboState]
    set schematic [$design GetSchematic [cs $schematicName] $state];check $state
    if {$schematic eq "NULL"} {error "object_not_found"}
    set page [$schematic GetPage [cs $pageName] $state];check $state
    if {$page eq "NULL"} {error "object_not_found"}
    set iterator [$page NewPartInstsIter $state];check $state
    set matches {}
    try {
        set count 0
        for {set part [$iterator NextPartInst $state]} {$part ne "NULL"} {set part [$iterator NextPartInst $state]} {
            check $state
            if {[incr count]>10000} {error "result_limit"}
            set text [cs ""]; $part GetReference $text
            if {[DboTclHelper_sGetConstCharPtr $text] eq $reference} {lappend matches $part}
        }
    } finally {delete_DboPagePartInstsIter $iterator}
    if {[llength $matches] != 1} {error "ambiguous_target"}
    return [list $schematic $page [lindex $matches 0]]
}
proc ::cmcpProperty::read {part} {
    set value [cs ""]
    set state [$part GetEffectivePropStringValue [cs MCP_NOTE] $value]
    if {[$state Failed]} {return [list 0 ""]}
    return [list 1 [DboTclHelper_sGetConstCharPtr $value]]
}
proc ::cmcpProperty::save {design schematic page} {
    set session $::DboSession_s_pDboSession
    DboSession -this $session
    check [$page MarkModified]
    check [$schematic MarkModified $page]
    check [$schematic SavePage $page]
    check [$design SaveSchematic $schematic]
    check [$session MarkAllLibForSave $design]
    check [$session SaveDesign $design]
}
