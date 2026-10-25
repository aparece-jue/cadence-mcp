# Owned fixture only. Source library must be a private copy.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2};lassign $argv root library target output
if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
proc cmcp::pt {x y} {return [DboTclHelper_sMakeCPoint $x $y]}
set log [open [file join [file dirname $target] phases.log] {WRONLY CREAT EXCL}]
proc cmcp::phase {value} {global phase log;set phase $value;puts $log $phase;flush $log}
set phase init;set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 cmcp::phase create_design
 set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs TOP]];cmcp::check $state
 set sch [$d GetRootSchematic $state];cmcp::check $state
 set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 set off [$lib GetOffPageSymbol [cmcp::cs OFFPAGELEFT-L] $state];cmcp::check $state
 set supply [$lib GetGlobalSymbol [cmcp::cs VCC] $state];cmcp::check $state
 cmcp::phase copy_symbols
 set copied [$d CopySymbol $off [cmcp::cs MCP_OFF] $state];cmcp::check $state
 set copied [$d CopySymbol $supply [cmcp::cs MCP_SUPPLY] $state];cmcp::check $state
 set off [$d GetOffPageSymbol [cmcp::cs MCP_OFF] $state];cmcp::check $state
 set supply [$d GetGlobalSymbol [cmcp::cs MCP_SUPPLY] $state];cmcp::check $state
 foreach pageName {PAGE_A PAGE_B} {
  cmcp::phase "create_page_$pageName"
  set p [$sch NewPage $state [cmcp::cs $pageName]];cmcp::check $state
  foreach {y category} {100 link 200 different 300 power 400 casefold} {
   cmcp::phase "symbol_${pageName}_$category"
   switch -- $category {
    link {set name MCP_LINK}
    different {set name [expr {$pageName eq "PAGE_A" ? "MCP_LEFT" : "MCP_RIGHT"}]}
    power {set name MCP_POWER}
    casefold {set name [expr {$pageName eq "PAGE_A" ? "MCP_CASE" : "mcp_case"}]}
   }
   if {$category eq "power"} {set obj [$p NewGlobal $state [cmcp::cs $name] $supply [cmcp::pt 90 $y] 0 0]} else {set obj [$p NewOffPageConnector $state [cmcp::cs $name] $off [cmcp::pt 100 $y] 0 0]};cmcp::check $state
   if {$obj eq "NULL"} {error no_symbol}
   cmcp::phase "wire_${pageName}_$category"
   set w [$p NewWireScalar $state [cmcp::pt 100 [expr {$y+10}]] [cmcp::pt 200 [expr {$y+10}]]];cmcp::check $state
   cmcp::check [$p MarkModified]
  }
  cmcp::phase "save_page_$pageName"
  cmcp::check [$sch MarkModified $p];cmcp::check [$sch SavePage $p]
 }
 cmcp::phase save_schematic;cmcp::check [$d SaveSchematic $sch]
 cmcp::phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {exit 1}
