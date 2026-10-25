# Fixed analog engine analysis, enum selection only; owned circuit/output paths.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root circuit directory analysis
if {$analysis ni {dc ac transient}} {exit 2}
set command [dict get {dc doDCAN ac doACAN transient DoTRAN} $analysis]
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
    set value [PSpiceSetupAnalysis $circuit [file join $directory result.out] [file join $directory result.dat] [file join $root tools pspice library]]
    lappend values setupReturn [cmcp::q $value]
    if {![string is integer -strict $value] || $value!=0} {error setup_analysis_failed}
    phase run_analysis
    set value [PSpiceCommandDo $command true]
    lappend values analysisReturn [cmcp::q $value]
    if {![string is integer -strict $value] || $value!=0} {error analysis_failed}
    phase finish
    set value [PSpiceCommandDo FINISH true]
    lappend values finishReturn [cmcp::q $value]
    if {![string is integer -strict $value] || $value!=0} {error finish_failed}
    phase cleanup
    set value [PSpiceTranEnd]
    lappend values cleanupReturn [cmcp::q $value]
    phase complete
} message]
close $stream
set out [open [file join $directory receipt.json] {WRONLY CREAT EXCL}]
try {fconfigure $out -encoding utf-8 -translation lf;puts $out [cmcp::obj caught $rc message [cmcp::q [string range $message 0 2047]] returns [cmcp::obj {*}$values]]} finally {close $out}
if {$rc} {exit 1}
