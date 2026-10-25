# Original fixed synthetic two-block complex oracle, using documented DAT version9.
# Private acceptance fixture only; this is not a simulation or public DAT write tool.
if {$argc!=2} {exit 2};lassign $argv install directory
set target [file join $directory complex.dat];if {[file exists $target]} {exit 2}
set log [open [file join $directory fixture.log] {WRONLY CREAT EXCL}];fconfigure $log -encoding utf-8 -translation lf
proc step {method args} {
 global log
 puts $log [list enter $method {*}$args];flush $log
 set value [writer $method {*}$args]
 puts $log [list leave $method $value];flush $log
 if {![string is boolean -strict $value] || !$value} {error "native_fixture_step_failed_$method"}
 return $value
}
set rc [catch {
 load [file join $install tools bin orevalexpr64.dll]
 orExprEval writer
 step create $target 9
 for {set block 0} {$block<2} {incr block} {
  step addBlock
  foreach {key value} {CircuitName MCP_FIXTURE RevisionNumber 24.1 ComplexFlag 2 DataType 0 AnalysisName {AC Analysis} DotProbeWithVariables 1 NumberofAnalogColumns 2 SweepMode 2 PrimaryParamName Frequency StartingSweepValue 10 EndingSweepValue 30 Temperature 27 ProgramID 45645} {step setHeaderData $key $value}
  step addDataName Frequency 0;step addDataName Gain 0
  foreach frequency {10 20 30} {step addTimePoint $frequency 0;step addDataPoint [expr {$frequency+$block*100}] [expr {-$frequency/10.0-$block}]}
  step closeBlock
 }
 step closeFile
} message]
puts $log [list completed [expr {!$rc}] error [expr {$rc ? $message : ""}]];close $log
if {$rc} {exit 1}
