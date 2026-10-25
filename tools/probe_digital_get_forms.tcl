# Private fixed calls based on installed QuickView sample, no public eval.
if {$argc!=4} {error "install copied-dat output json-helper"}
lassign $argv install data output helper
source $helper
load [file join $install tools bin orPIOData64.dll]
orPIOObject reader
if {![reader loadFile $data] || ![reader setBlock 0]} {error load_failed}
set rows {}
set log [open [file join [file dirname $output] calls.log] {WRONLY CREAT EXCL}]
foreach call {
 {get Time}
 {get V(ANALOG)}
 {get DIN}
 {get MISSING_TRACE_60}
 {getR V(ANALOG) 5}
 {getR DIN 5}
 {get DIN Time 5 0 0.000004 0 0 TimeVector aa bb}
 {get V(ANALOG) Time 5 0 0.000004 0 0 TimeVector aa bb}
} {
 puts $log [list before {*}$call];flush $log
 set caught [catch {reader {*}$call} value]
 puts $log [list after {*}$call caught $caught length [string length $value]];flush $log
 set arrays {}
 foreach array {TimeVector aa bb} {
  set values {}
  if {[array exists ::$array]} {
   foreach key [lsort -integer [array names ::$array]] {
    if {[llength $values]>=30} {break}
    lappend values [cmcp::obj index [cmcp::q $key] value [cmcp::q [set ::${array}($key)]]]
   }
  }
  lappend arrays [cmcp::obj name [cmcp::q $array] size [array size ::$array] values [cmcp::arr $values]]
  unset -nocomplain ::$array
 }
 lappend rows [cmcp::obj call [cmcp::q $call] caught $caught length [string length $value] value [cmcp::q $value] arrays [cmcp::arr $arrays]]
}
reader close
close $log
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows]} finally {close $f}
