# Fixed native merged-configuration query; never generates CIR or runs a solver.
source [file join [file dirname [info script]] json.tcl]
lassign $argv install project profile ini output
set obj {};set phase load
set caught [catch {
 foreach {dll init} {orPSpiceExplorer64.dll orPSpiceExplorer orCommonTcl64.dll orCommonTcl orSimSrvr64.dll orSimSrvr} {load [file join $install tools bin $dll] $init}
 set phase construct;set empty {};set obj [new_CorSimSrvr $empty 2]
 set phase ini;CorSimSrvr_setIniFile $obj $ini
 set phase profile;set loaded [$obj loadProfile $profile]
 set before {};set ignored [$obj readSettingsToJSON before]
 set phase libinc;set libraries [$obj readSettingsLibinc $project $profile]
 set after {};set ignored [$obj readSettingsToJSON after]
 if {[string length $before]>1048576 || [string length $after]>1048576} {error settings_json_limit}
 set phase returned
 set result [cmcp::obj pid [pid] returned true loadResult [cmcp::q $loaded] libincResult [cmcp::q $libraries] beforeJSON [cmcp::q $before] afterJSON [cmcp::q $after]]
} message]
if {$obj ne {}} {if {[catch {delete_CorSimSrvr $obj} cleanup] && !$caught} {set caught 1;set phase cleanup;set message $cleanup}}
if {$caught} {set result [cmcp::obj pid [pid] returned false phase [cmcp::q $phase] error [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f $result} finally {close $f}
if {$caught} {exit 1}
