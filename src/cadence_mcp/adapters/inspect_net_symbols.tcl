# Read only an owned OLB copy, enumerating actual net-symbol definitions.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root source output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase opening
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $source] $state];cmcp::check $state
 if {$lib eq "NULL"} {error missing_library}
 set phase symbols;set it [$lib NewSymbolsIter $state];cmcp::check $state;set rows {};set count 0
 try {
  for {set sym [$it NextSymbol $state]} {$sym ne "NULL"} {set sym [$it NextSymbol $state]} {
   cmcp::check $state;if {[incr count]>10000} {error symbol_limit}
   set n [cmcp::cs ""];cmcp::check [$sym GetName $n]
   lappend rows [cmcp::obj name [cmcp::q [DboTclHelper_sGetConstCharPtr $n]] objectType [$sym GetObjectType]]
  }
 } finally {delete_DboLibSymbolsIter $it}
 set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows];close $f
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set f [open "$output.error.json" {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj phase [cmcp::q $phase] message [cmcp::q $message]];close $f;exit 1}
