# Capability inventory only. Does not open a design or call any netlist operation.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv root kind output
if {$kind ni {pspice tclnetlist}} {exit 2}
set phase load_dbo;set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 proc cmcp::allCommands {{namespace ::} {depth 0}} {
  if {$depth>10} {error namespace_limit};set result [info commands ${namespace}*]
  foreach child [namespace children $namespace] {lappend result {*}[cmcp::allCommands ${child}:: [expr {$depth+1}]]}
  return [lsort -unique $result]
 }
 set before [cmcp::allCommands];set beforePackages [package names]
 if {$kind eq "pspice"} {set dll orPspNetlist64.dll;set init orPspNetList} else {set dll orTclNetlist64.dll;set init orTclNetlist}
 set phase load_netlist;set loaded [catch {load [file join $root tools bin $dll] $init} loadMessage]
 set commands {};foreach command [cmcp::allCommands] {
  if {$command ni $before && ![string match ::cmcp::* $command]} {lappend commands [cmcp::q $command]}
 }
 set packages {};foreach package [lsort [package names]] {if {$package ni $beforePackages} {lappend packages [cmcp::q $package]}}
 set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
 puts $f [cmcp::obj dll [cmcp::q $dll] loadSucceeded [expr {$loaded ? "false" : "true"}] loadMessage [cmcp::q [string range $loadMessage 0 2047]] newCommands [cmcp::arr $commands] newPackages [cmcp::arr $packages] netlistExecuted false designOpened false];close $f
} message]
if {$rc} {set f [open "$output.error.json" {WRONLY CREAT EXCL}];puts $f [cmcp::obj phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f;exit 1}

