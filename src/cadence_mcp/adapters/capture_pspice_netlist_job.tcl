# Fixed native NET/ALS operation in an authenticated, already running Capture host.
# Arguments are data from a trusted generated wrapper, never MCP script input.
namespace eval ::cmcpNativeNetlist {
 proc run {expectedPid active design target output marker nonce dll} {
  if {[pid] != $expectedPid} {error wrong_process}
  if {![regexp {^[a-f0-9]{32}$} $nonce]} {error invalid_job_nonce}
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]]} {error wrong_active_design}
  if {[info exists ::cmcpBridge::propertyPlans] && [dict size $::cmcpBridge::propertyPlans]} {error bridge_busy}
  if {[file exists $output] || [file exists $marker]} {error already_dispatched}
  if {[file exists $target] || [file exists [file rootname $target].als]} {error output_exists}
  set f [open $marker {WRONLY CREAT EXCL}];puts $f $nonce;close $f
  set native {};set phase load
  set caught [catch {
   if {![llength [info commands ::OrTclNetlist_sCreatePSpiceNetList]]} {load $dll orTclNetlist}
   set phase generate
   set native [::OrTclNetlist_sCreatePSpiceNetList $design $target false false false false true true {}]
   set phase returned
  } message]
  set logs {};set totalLogChars 0
  foreach {category command} {errors ::OrTclNetlist_sGetErrorLog warnings ::OrTclNetlist_sGetWarningLog session ::OrTclNetlist_sGetSessionLog netlist ::OrTclNetlist_sGetNetlistLog} {
   set values {};set readable 0
   set logCaught [catch {
    set vector [DboTclHelper_sMakeStdVector];$command $vector
    set size [DboTclHelper_sGetVectorSize $vector]
    if {![string is integer -strict $size] || $size<0 || $size>1000} {error log_limit}
    for {set i 0} {$i<$size} {incr i} {
     set line [DboTclHelper_sGetConstCharPtrFromVector $vector $i]
     if {[string length $line]>4096} {error log_line_limit}
     incr totalLogChars [string length $line]
     if {$totalLogChars>131072} {error total_log_limit}
     lappend values [cmcp::q $line]
    }
    set readable 1
   } ignored]
   lappend logs [cmcp::obj category [cmcp::q $category] readable [expr {$readable?"true":"false"}] lines [cmcp::arr $values]]
  }
  set receipt [cmcp::obj jobId [cmcp::q $nonce] pid [pid] invocationReturned [expr {$caught?"false":"true"}] phase [cmcp::q $phase] nativeReturn [cmcp::q $native] error [cmcp::q [expr {$caught?[string range $message 0 2047]:{}}]] logs [cmcp::arr $logs]]
  set pending ${output}.pending
  set f [open $pending {WRONLY CREAT EXCL}]
  try {fconfigure $f -encoding utf-8 -translation lf;puts $f $receipt} finally {close $f}
  file rename $pending $output
 }
}
