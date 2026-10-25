# Manual test helper only, never registered with the bridge dispatcher.
namespace eval ::fixtureDirtyProbe {variable attempts 0}
proc ::fixtureDirtyProbe::start {design phaseFile} {
    variable expected; variable phase; variable attempts
    set expected [file normalize $design]; set phase [file normalize $phaseFile];set attempts 0
    after 250 ::fixtureDirtyProbe::poll
}
proc ::fixtureDirtyProbe::poll {} {
    variable expected;variable phase;variable attempts
    if {[incr attempts]>600} {puts FIXTURE_PROBE_EXPIRED;return}
    if {![file exists $phase]} {after 250 ::fixtureDirtyProbe::poll;return}
    if {![string equal -nocase [::cmcpBridge::activeDesign] $expected] || [::cmcpBridge::dirty] ne "clean"} {
        puts FIXTURE_PROBE_REFUSED;return
    }
    set design [GetActivePMDesign];set state [DboState]
    set occurrence [$design GetRootOccurrence $state]
    if {[$state Failed] || $occurrence eq "NULL"} {puts FIXTURE_PROBE_NO_ROOT;return}
    after 5000 [list $design ClearModified]
    $design MarkModified $occurrence
    puts "FIXTURE_PROBE_ACTUAL_STATE [::cmcpBridge::dirty]"
}
