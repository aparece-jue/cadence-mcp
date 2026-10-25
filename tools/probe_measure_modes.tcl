# Fixed official complete-analysis entry points; private native discovery only.
if {$argc!=5} {error "install circuit directory mode helper"}
lassign $argv install circuit directory mode helper
if {$mode ni {doall direct}} {error invalid_mode}
source $helper
set rc [catch {
 load [file join $install tools bin orPSP_ENG64.dll] orpspeng
 set batch [PSpiceSetLicenseBatchMode PSpiceAD]
 if {$mode eq "doall"} {
  set setup [PSpiceSetupAnalysis $circuit [file join $directory result.out] [file join $directory result.dat] [file join $install tools pspice library]]
  if {$setup!=0} {error setup_failed}
  set result [PSpiceCommandDo doALL true]
 } else {
  set setup not_applicable
  set result [PSpiceDoAnalysis $circuit [file join $directory result.out] [file join $directory result.dat] [file join $install tools pspice library]]
 }
 set finish [PSpiceCommandDo FINISH true]
 set cleanup [PSpiceTranEnd]
} message]
set f [open [file join $directory receipt.json] {WRONLY CREAT EXCL}]
set fields [list caught $rc message [cmcp::q $message]]
foreach name {batch setup result finish cleanup} {
 if {[info exists $name]} {lappend fields $name [cmcp::q [set $name]]}
}
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj {*}$fields]} finally {close $f}
if {$rc} {exit 1}
