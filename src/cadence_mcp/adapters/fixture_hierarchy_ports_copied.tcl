# Fixed fresh parent/child fixture. No existing design is opened or overwritten.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root library target output
if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::pt {x y} {return [DboTclHelper_sMakeCPoint $x $y]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set phaseLog [open [file join [file dirname $target] phases.log] {WRONLY CREAT EXCL}]
proc cmcp::phaseTrace {args} {global phase phaseLog;puts $phaseLog $phase;flush $phaseLog}
set session "";set phase load
trace add variable phase write cmcp::phaseTrace
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set phase create_design
 set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs TOP]];cmcp::check $state
 set top [$d GetRootSchematic $state];cmcp::check $state
 set parent [$top NewPage $state [cmcp::cs MAIN]];cmcp::check $state
 set phase create_child
 set child [$d NewSchematic [cmcp::cs CHILD] $state];cmcp::check $state
 set page [$child NewPage $state [cmcp::cs CHILD_PAGE]];cmcp::check $state
 set phase open_library
 set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 set phase get_port_source
 set source [$lib GetPortSymbol [cmcp::cs PORTLEFT-L] $state];cmcp::check $state
 if {$source eq "NULL" || [$source GetObjectType]!=34} {error invalid_port_source}
 set phase copy_input_symbol
 set copied [$d CopySymbol $source [cmcp::cs MCP_INPUT] $state];cmcp::check $state
 set phase copy_output_symbol
 set copied [$d CopySymbol $source [cmcp::cs MCP_OUTPUT] $state];cmcp::check $state
 set input [$d GetPortSymbol [cmcp::cs MCP_INPUT] $state];cmcp::check $state
 set outputSymbol [$d GetPortSymbol [cmcp::cs MCP_OUTPUT] $state];cmcp::check $state
 set phase create_child_input
 set inp [$page NewPort $state [cmcp::cs IN] $input [cmcp::pt 100 100]];cmcp::check $state
 set phase set_child_input_type;cmcp::check [$inp SetPinType 0]
 set phase create_child_output
 set outp [$page NewPort $state [cmcp::cs OUT] $outputSymbol [cmcp::pt 300 100]];cmcp::check $state
 set phase set_child_output_type;cmcp::check [$outp SetPinType 1]
 set phase child_wire
 set w [$page NewWireScalar $state [cmcp::pt 100 110] [cmcp::pt 300 110]];cmcp::check $state
 set phase create_parent_block
 set block [$parent NewDrawnInst $state [cmcp::cs BLOCK_A] [DboTclHelper_sMakeCRect 0 0 100 100] [cmcp::pt 400 300]];cmcp::check $state
 cmcp::check [$block SetReference [cmcp::cs BLOCK_A]]
 foreach {key value} {{Primitive} NO {Implementation Type} {Schematic View} Implementation CHILD {Implementation Path} {}} {
  set phase "implementation_$key";cmcp::check [$block SetEffectivePropStringValue [cmcp::cs $key] [cmcp::cs $value]]
 }
 set phase parent_input
 set pin [$block NewPortInstScalar $state [cmcp::cs IN] 0 [cmcp::pt 10 20] [cmcp::pt 0 20] 1];cmcp::check $state
 set phase parent_output
 set pin [$block NewPortInstScalar $state [cmcp::cs OUT] 1 [cmcp::pt 90 20] [cmcp::pt 100 20] 1];cmcp::check $state
 set phase save_symbols
 cmcp::check [$d SavePortSymbol $input];cmcp::check [$d SavePortSymbol $outputSymbol]
 set phase save_child
 cmcp::check [$page MarkModified];cmcp::check [$child MarkModified $page];cmcp::check [$child SavePage $page];cmcp::check [$d SaveSchematic $child]
 set phase save_parent
 cmcp::check [$parent MarkModified];cmcp::check [$top MarkModified $parent];cmcp::check [$top SavePage $parent];cmcp::check [$d SaveSchematic $top]
 set phase save_design
 cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf
puts $f [cmcp::obj saved [expr {$rc ? "false" : "true"}] phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f
if {$rc} {puts stderr [string range [dict get $options -errorinfo] 0 2047];exit 1}
