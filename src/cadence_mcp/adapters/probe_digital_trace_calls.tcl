source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv root data output
load [file join $root tools bin orPIOData64.dll]
set log [open [file join [file dirname $output] calls.log] {WRONLY CREAT EXCL}];fconfigure $log -encoding utf-8 -translation lf
orPIOObject reader
if {![reader loadFile $data]} {exit 1};reader setBlock 0
set rows {}
foreach call {{get INIT} {get RUN} {get MODE} {get {D(INIT)}} {get {V(INIT)}} {get DigitalTime} {get DTime} {get {Time;Digital}} {getR INIT 10} {getR RUN 10}} {
 puts $log [list before {*}$call];flush $log
 set rc [catch {reader {*}$call} value]
 puts $log [list after {*}$call caught $rc length [string length $value]];flush $log
 lappend rows [cmcp::obj call [cmcp::q $call] caught $rc length [string length $value] prefix [cmcp::q [string range $value 0 800]]]
}
reader close;close $log
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows]} finally {close $f}
