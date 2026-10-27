# Fixed CorSimSrvr operation. Input files belong to a new private task copy.
namespace eval ::cmcpProfileCircuit {
 proc run {install project profile ini expectedCir output nonce} {
  if {![regexp {^[a-f0-9]{32}$} $nonce]} {error invalid_job_nonce}
  foreach input [list $project $profile $ini] {
   if {![file isfile $input]} {error missing_profile_input}
  }
  foreach target [list $expectedCir $output ${output}.pending] {
   if {[file exists $target]} {error preexisting_profile_output}
  }
  if {![file isdirectory [file dirname $expectedCir]]} {error missing_output_directory}
  set phase load;set obj {};set loaded {};set libraries {};set updated {};set cir {}
  set caught [catch {
   foreach {dll init} {orPSpiceExplorer64.dll orPSpiceExplorer orCommonTcl64.dll orCommonTcl orSimSrvr64.dll orSimSrvr} {
    load [file join $install tools bin $dll] $init
   }
   set phase construct;set empty {};set obj [new_CorSimSrvr $empty 2]
   set phase bind_private_ini;CorSimSrvr_setIniFile $obj $ini
   set phase load_profile;set loaded [$obj loadProfile $profile]
   set phase read_libinc;set libraries [$obj readSettingsLibinc $project $profile]
   set phase update_cir;set updated [$obj updateCirFileI cir]
   if {$loaded ne {0} || $libraries ne {0} || $updated ne {0}} {error native_profile_failure}
   if {![string equal -nocase [file normalize $cir] [file normalize $expectedCir]]} {error unexpected_circuit_path}
   if {![file isfile $expectedCir] || [file size $expectedCir]<=0} {error missing_generated_circuit}
   set phase returned
  } message]
  if {$obj ne {}} {
   if {[catch {delete_CorSimSrvr $obj} cleanup] && !$caught} {set caught 1;set phase cleanup;set message $cleanup}
  }
  set receipt [cmcp::obj jobId [cmcp::q $nonce] pid [pid] invocationReturned [expr {$caught?"false":"true"}] phase [cmcp::q $phase] iniSelectionVerified false loadResult [cmcp::q $loaded] libincResult [cmcp::q $libraries] updateResult [cmcp::q $updated] cirPath [cmcp::q $cir] error [cmcp::q [expr {$caught?[string range $message 0 2047]:{}}]]]
  set f [open ${output}.pending {WRONLY CREAT EXCL}]
  try {fconfigure $f -encoding utf-8 -translation lf;puts $f $receipt} finally {close $f}
  file rename ${output}.pending $output
  if {$caught} {error profile_circuit_failed}
 }
}
