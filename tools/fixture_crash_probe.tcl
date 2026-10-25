# Manual-only inventory for a controlled crash of a test-only Capture process.
# No terminate/exit operation is exposed to MCP or implemented here.
namespace eval ::fixtureCrash {variable ticks 0}
proc ::fixtureCrash::write {file data} {
    set stream [open $file {WRONLY CREAT EXCL}]
    try {fconfigure $stream -encoding utf-8 -translation lf;puts $stream $data} finally {close $stream}
}
proc ::fixtureCrash::inventory {} {
    variable output
    set session $::DboSession_s_pDboSession;DboSession -this $session
    set state [DboState];set result {};set libs {}
    set iterator [$session NewDesignsIter $state];::cmcpBridge::stateCheck $state
    try {
        for {set design [$iterator NextDesign $state]} {$design ne "NULL"} {set design [$iterator NextDesign $state]} {
            ::cmcpBridge::stateCheck $state
            set name [DboTclHelper_sMakeCString];$design GetName $name
            set dirty [$design IsModified $state];::cmcpBridge::stateCheck $state
            lappend result [cmcp::obj path [cmcp::q [file normalize [DboTclHelper_sGetConstCharPtr $name]]] dirty [expr {$dirty ? "true" : "false"}]]
            if {[llength $result]>100} {error "inventory_limit"}
        }
    } finally {delete_DboSessionDesignsIter $iterator}
    set iterator [$session NewLibsIter $state];::cmcpBridge::stateCheck $state
    try {
        for {set lib [$iterator NextLib $state]} {$lib ne "NULL"} {set lib [$iterator NextLib $state]} {
            ::cmcpBridge::stateCheck $state
            set name [DboTclHelper_sMakeCString];$lib GetName $name
            set dirty [$lib IsModified $state];::cmcpBridge::stateCheck $state
            lappend libs [cmcp::obj path [cmcp::q [DboTclHelper_sGetConstCharPtr $name]] dirty [expr {$dirty ? "true" : "false"}]]
            if {[llength $libs]>1000} {error "inventory_limit"}
        }
    } finally {delete_DboSessionLibsIter $iterator}
    write [file join $output crash-inventory.json] [cmcp::obj pid [pid] timeMs [clock milliseconds] designs [cmcp::arr $result] libraries [cmcp::arr $libs]]
}
proc ::fixtureCrash::poll {} {
    variable output;variable ticks
    if {[incr ticks]>1200} {return}
    if {![file exists [file join $output inventory-request.json]]} {after 100 ::fixtureCrash::poll;return}
    if {[catch {inventory} message]} {write [file join $output inventory-error.json] [cmcp::obj failed true]}
}
proc ::fixtureCrash::start {directory} {
    variable output;variable ticks
    set output [file normalize $directory];set ticks 0
    after 100 ::fixtureCrash::poll
    puts FIXTURE_CRASH_INVENTORY_ARMED
}
