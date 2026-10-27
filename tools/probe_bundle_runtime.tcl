source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=2} {exit 2}
lassign $argv root output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set variables {};set commands {}
foreach name [lsort [info globals *DboBundleType*]] {if {![array exists ::$name]} {lappend variables [cmcp::obj name [cmcp::q $name] value [cmcp::q [set ::$name]]]}}
foreach pattern {*bool* *Bool* DboTclHelper_sMake* DboBundleTemplateMap*} {
 foreach name [lsort [info commands $pattern]] {lappend commands [cmcp::q $name]}
}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj variables [cmcp::arr $variables] commands [cmcp::arr $commands]]} finally {close $f}
