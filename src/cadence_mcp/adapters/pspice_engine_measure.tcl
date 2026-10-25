# Fixed complete-analysis entry point; outputs only in the owned task directory.
if {$argc!=3} {exit 2}
lassign $argv install circuit directory
source [file join [file dirname [info script]] json.tcl]
set analysisReturn missing;set cleanupReturn missing
set rc [catch {
 load [file join $install tools bin orPSP_ENG64.dll] orpspeng
 PSpiceSetLicenseBatchMode PSpiceAD
 set analysisReturn [PSpiceDoAnalysis $circuit [file join $directory result.out] [file join $directory result.dat] [file join $install tools pspice library]]
 if {![string is integer -strict $analysisReturn] || $analysisReturn!=0} {error analysis_failed}
 # PSpiceDoAnalysis finishes/closes internally; an extra FINISH returns1.
 set cleanupReturn [PSpiceTranEnd]
 if {$cleanupReturn!=0} {error cleanup_failed}
} message]
set f [open [file join $directory receipt.json] {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj entryPoint [cmcp::q PSpiceDoAnalysis] caught $rc analysisReturn [cmcp::q $analysisReturn] cleanupReturn [cmcp::q $cleanupReturn] message [cmcp::q [string range $message 0 2047]]]} finally {close $f}
if {$rc} {exit 1}
