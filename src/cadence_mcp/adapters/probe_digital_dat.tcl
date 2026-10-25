# Private read-only digital/mixed DAT representation probe; no public decoder changes.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv install data output
load [file join $install tools bin orPIOData64.dll]
set traceLog [open [file join [file dirname $output] trace.log] {WRONLY CREAT EXCL}];fconfigure $traceLog -encoding utf-8 -translation lf
orPIOObject reader
proc traceReader {args} {
 global traceLog
 set operation [lindex $args end]
 if {$operation eq "enter"} {puts $traceLog [list enter [lindex $args 0]]} else {puts $traceLog [list leave [lindex $args 0] code [lindex $args 1] resultLength [string length [lindex $args 2]]]}
 flush $traceLog
}
trace add execution reader {enter leave} traceReader
set closeAttempted 0
set rows {};set rc [catch {
 if {![reader loadFile $data]} {error load_failed}
 set count [reader getNumberofBlocks];if {![string is integer -strict $count] || $count<1 || $count>128} {error block_limit}
 for {set block 0} {$block<$count} {incr block} {
  if {![reader setBlock $block]} {error set_block_failed}
  set fields {}
  foreach key {ComplexFlag DataType NumberofAnalogRows NumberofAnalogColumns NumberofDigitalRows NumberofDigitalColumns PrimaryParamName AnalysisName} {
   set code [catch {reader getHeaderData $key} value]
   lappend fields [cmcp::obj key [cmcp::q $key] caught $code value [cmcp::q $value]]
  }
  set groups {}
  foreach type {0 1 2} {
   set code [catch {reader getDataNames $type} names]
   set samples {}
   if {!$code} {
    foreach name [lrange $names 0 2] {
     set caught [catch {reader get $name} values]
     lappend samples [cmcp::obj name [cmcp::q $name] caught $caught length [string length $values] prefix [cmcp::q [string range $values 0 400]]]
    }
   }
   lappend groups [cmcp::obj type $type caught $code names [cmcp::q $names] samples [cmcp::arr $samples]]
  }
  lappend rows [cmcp::obj block $block fields [cmcp::arr $fields] groups [cmcp::arr $groups]]
 }
 set closeAttempted 1;reader close
} error]
if {!$closeAttempted} {set closeAttempted 1;catch {reader close}}
close $traceLog
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj caught $rc error [cmcp::q [expr {$rc ? $error : ""}]] blocks [cmcp::arr $rows]]} finally {close $f}
if {$rc} {exit 1}
