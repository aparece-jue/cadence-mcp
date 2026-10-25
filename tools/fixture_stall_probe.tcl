# Manual, fixture-only fault injection. Never registered as an MCP operation.
namespace eval ::fixtureStall {variable ticks 0}
proc ::fixtureStall::write {path value} {
    set stream [open $path {WRONLY CREAT EXCL}]
    try {fconfigure $stream -encoding utf-8 -translation lf;puts $stream $value} finally {close $stream}
}
proc ::fixtureStall::inventory {} {
    variable directory
    set session $::DboSession_s_pDboSession;DboSession -this $session
    set state [DboState];set iterator [$session NewDesignsIter $state]
    ::cmcpBridge::stateCheck $state
    set designs {}
    try {
        for {set design [$iterator NextDesign $state]} {$design ne "NULL"} {set design [$iterator NextDesign $state]} {
            ::cmcpBridge::stateCheck $state
            set name [DboTclHelper_sMakeCString];$design GetName $name
            set dirty [$design IsModified $state];::cmcpBridge::stateCheck $state
            lappend designs [cmcp::obj path [cmcp::q [file normalize [DboTclHelper_sGetConstCharPtr $name]]] dirty [expr {$dirty ? "true" : "false"}]]
            if {[llength $designs]>100} {error "inventory_limit"}
        }
    } finally {delete_DboSessionDesignsIter $iterator}
    write [file join $directory inventory.json] [cmcp::obj pid [pid] designs [cmcp::arr $designs]]
}
proc ::fixtureStall::poll {} {
    variable directory;variable expected;variable ticks
    if {[incr ticks]>600} {return}
    if {![file exists [file join $directory ready.json]]} {after 100 ::fixtureStall::poll;return}
    if {![string equal -nocase [::cmcpBridge::activeDesign] $expected] || [::cmcpBridge::dirty] ne "clean"} {error "fixture_target_changed"}
    write [file join $directory block-started.json] [cmcp::obj timeMs [clock milliseconds]]
    after 12000
    write [file join $directory block-ended.json] [cmcp::obj timeMs [clock milliseconds]]
}
proc ::fixtureStall::start {design output} {
    variable directory;variable expected;variable ticks
    set expected [file normalize $design];set directory [file normalize $output];set ticks 0
    inventory
    after 100 ::fixtureStall::poll
    puts FIXTURE_STALL_ARMED
}
