# Fixed DC-only engine probe, owned circuit/output paths supplied by host.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root circuit directory
set stream [open [file join $directory phases.log] {WRONLY CREAT EXCL}]
fconfigure $stream -encoding utf-8 -translation lf
proc phase {name} {global stream;puts $stream $name;flush $stream}
set values {}
set rc [catch {
    phase load_engine
    load [file join $root tools bin orPSP_ENG64.dll] orpspeng
    phase batch_license_mode
    set value [PSpiceSetLicenseBatchMode PSpiceAD]
    lappend values batchModeReturn [cmcp::q $value]
    phase setup_analysis
    set value [PSpiceSetupAnalysis $circuit [file join $directory dc.out] [file join $directory dc.dat] [file join $root tools pspice library]]
    lappend values setupReturn [cmcp::q $value]
    phase run_dc
    set value [PSpiceCommandDo doDCAN true]
    lappend values dcReturn [cmcp::q $value]
    phase finish
    set value [PSpiceCommandDo FINISH true]
    lappend values finishReturn [cmcp::q $value]
    phase cleanup
    set value [PSpiceTranEnd]
    lappend values cleanupReturn [cmcp::q $value]
    phase complete
} message]
close $stream
set out [open [file join $directory receipt.json] {WRONLY CREAT EXCL}]
try {fconfigure $out -encoding utf-8 -translation lf;puts $out [cmcp::obj caught $rc message [cmcp::q [string range $message 0 2047]] returns [cmcp::obj {*}$values]]} finally {close $out}
if {$rc} {exit 1}
