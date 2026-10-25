# Fixed wrong-arity diagnostics only; 100 arguments cannot match these fixed APIs.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2};lassign $argv root kind output
if {$kind ni {pspice tclnetlist}} {exit 2}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
if {$kind eq "pspice"} {load [file join $root tools bin orPspNetlist64.dll] orPspNetList;set commands {new_pspNetlist pspNetlist_init pspNetlist_createNetlist pspNetlist_createNetlistExt pspNetlist_setProjDir pspNetlist_setDesignLibPath pspNetlist_setProjectLibPath pspNetlist_setSimProfLibPath pspNetlist_analyzeDesign}} else {load [file join $root tools bin orTclNetlist64.dll] orTclNetlist;set commands {OrTclNetlist_sCreatePSpiceNetList OrTclNetlist_sGetNetlistLog}}
set rows {}
foreach command $commands {
 set code [catch {$command {*}[lrepeat 100 __CMCP_ARITY_ONLY__]} message]
 lappend rows [cmcp::obj command [cmcp::q $command] rejected [expr {$code ? "true" : "false"}] diagnostic [cmcp::q [string range $message 0 8191]]]
 if {!$code} {error unexpected_arity_acceptance}
}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::arr $rows];close $f
