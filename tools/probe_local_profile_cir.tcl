# Fixed local profile-to-CIR primitive sequence, based on installed official example.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
lassign $argv install project profile output marker
proc mark {phase} {global marker;set f [open $marker a];puts $f $phase;close $f}
set obj "";set rc [catch {
 foreach {dll init} {orPSpiceExplorer64.dll orPSpiceExplorer orCommonTcl64.dll orCommonTcl orSimSrvr64.dll orSimSrvr} {mark "load_$dll";load [file join $install tools bin $dll] $init}
 mark construct
 set empty {};set obj [new_CorSimSrvr $empty 2]
 mark load_profile
 set loaded [$obj loadProfile $profile]
 mark read_libinc
 set libraries [$obj readSettingsLibinc $project $profile]
 mark update_cir
 set cir {};set updated [$obj updateCirFileI cir]
 mark returned
 set result [cmcp::obj invocationReturned true loadResult [cmcp::q $loaded] libincResult [cmcp::q $libraries] updateResult [cmcp::q $updated] cirPath [cmcp::q $cir]]
} message]
if {$obj ne ""} {mark cleanup;catch {delete_CorSimSrvr $obj}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;if {$rc} {puts $f [cmcp::obj invocationReturned false error [cmcp::q $message]]} else {puts $f $result}} finally {close $f}
if {$rc} {exit 1}
