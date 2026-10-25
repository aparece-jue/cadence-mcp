# Test-only fake Capture context for transport/lifecycle tests. Never source in Capture.
set configFile [lindex $argv 0]
set adapter [lindex $argv 1]
while {![file exists $configFile]} {after 20}
package require json
set f [open $configFile];set cfg [::json::json2dict [read $f]];close $f
set ::fixturePath [dict get $cfg expectedDesign]
set ::fixtureDirty 0
proc GetActivePMDesign {} {return ::fakeDesign}
proc DboTclHelper_sMakeCString {args} {return fixtureString}
proc DboTclHelper_sGetConstCharPtr {value} {return $::fixtureString}
proc DboState {} {return ::fakeState}
proc ::fakeState {method args} {return 0}
proc ::fakeDesign {method args} {
    switch -- $method {
        GetName {set ::fixtureString $::fixturePath;return ::fakeState}
        IsModified {return $::fixtureDirty}
        default {error "unsupported fake design method"}
    }
}
proc fixtureControl {} {
    set path [file join [file dirname $::configFile] control.json]
    if {[file exists $path]} {
        if {![catch {set f [open $path];set c [::json::json2dict [read $f]];close $f}]} {
            set ::fixturePath [dict get $c path]
            set ::fixtureDirty [dict get $c dirty]
        }
    }
    after 25 fixtureControl
}
source $adapter
::cmcpBridge::start $configFile
fixtureControl
vwait ::forever
