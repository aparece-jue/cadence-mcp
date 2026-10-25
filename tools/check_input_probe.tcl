# Fixed parser/setup-only operation. No DC/AC/TRAN/OP execution command.
if {$argc!=4} {exit 2}
lassign $argv install circuit directory helper
source $helper
set setupReturn missing;set finishReturn missing;set cleanupReturn missing
set rc [catch {
 load [file join $install tools bin orPSP_ENG64.dll] orpspeng
 PSpiceSetLicenseBatchMode PSpiceAD
 set setupReturn [PSpiceSetupAnalysis $circuit [file join $directory result.out] [file join $directory setup.dat] [file join $install tools pspice library]]
 if {![string is integer -strict $setupReturn] || $setupReturn!=0} {error input_setup_failed}
 set finishReturn [PSpiceCommandDo FINISH true]
 if {$finishReturn!=0} {error input_finish_failed}
 set cleanupReturn [PSpiceTranEnd]
 if {$cleanupReturn!=0} {error input_cleanup_failed}
} message]
if {$rc} {catch {PSpiceCommandDo FINISH true};catch {PSpiceTranEnd}}
set f [open [file join $directory receipt.json] {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj entryPoint [cmcp::q PSpiceSetupAnalysis] caught $rc setupReturn [cmcp::q $setupReturn] finishReturn [cmcp::q $finishReturn] cleanupReturn [cmcp::q $cleanupReturn] analysisExecuted false message [cmcp::q [string range $message 0 2047]]]} finally {close $f}
if {$rc} {exit 1}
