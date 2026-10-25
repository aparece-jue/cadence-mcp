# Private fault harness: real Dbo traversal, one iterator state replaced at a boundary.
lassign $argv adapter install design output mode
namespace eval probe {variable mode;variable injected 0;variable serial 0;variable calls 0}
set probe::mode $mode
proc probe::bad {method args} {
 switch -- $method {OK {return 0} Failed {return 1} Code {return 3969} default {error bad_state_method}}
}
proc probe::iterator {original kind args} {
 variable mode;variable injected;variable calls
 set method [lindex $args 0]
 if {($kind eq "property" && $method eq "NextEffectiveProp") || ($kind eq "child" && $method eq "NextOccurrence")} {
  incr calls
  if {$calls==2} {
   set injected 1
   puts stderr "INJECTED:$kind:3969";flush stderr
   if {$kind eq "property"} {return probe::bad}
   set state [lindex $args 1];rename $state ${state}_probe_native;interp alias {} $state {} probe::bad
   return NULL
  }
 }
 return [$original {*}$args]
}
proc probe::occurrence {original args} {
 variable mode;variable injected;variable serial
 set result [$original {*}$args];set method [lindex $args 0]
 if {!$injected && (($mode eq "property" && $method eq "NewEffectivePropsIter") || ($mode eq "child" && $method eq "NewChildrenIter"))} {
  set native ${result}_probe_[incr serial];rename $result $native
  interp alias {} $result {} probe::iterator $native $mode
 }
 return $result
}
proc probe::enter {command op} {
 variable serial
 set occurrence [lindex $command 1]
 if {[string match *_probe_* $occurrence]} {error invalid_occurrence}
 set native ${occurrence}_probe_[incr serial];rename $occurrence $native
 interp alias {} $occurrence {} probe::occurrence $native
}
set f [open $adapter];set script [read $f];close $f
set script [string map [list {source [file join [file dirname [info script]] json.tcl]} [list source [file join [file dirname $adapter] json.tcl]]] $script]
set marker {if {$argc != 3}}
set at [string first $marker $script];if {$at<0} {error missing_adapter_boundary}
eval [string range $script 0 [expr {$at-1}]]
if {$mode ne "none"} {trace add execution cmcp::walk enter probe::enter}
set argv [list $install $design $output];set argc 3
eval [string range $script $at end]
