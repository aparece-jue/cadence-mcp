source [file join [file dirname [info script]] json.tcl]
if {$argc!=2} {exit 2}
lassign $argv root output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set rows {}
foreach quality {0 1 2 3 4 5 6} {
 set font [DboTclHelper_sMakeLOGFONT Arial 8 1 0 0 500 0 0 1 1 3 1 $quality 32]
 set actual [DboTclHelper_sGetLFQuality $font]
 set setters [info commands *sSetLFQuality*]
 lappend rows [cmcp::obj requested $quality constructed $actual setters [cmcp::arr [lmap c $setters {cmcp::q $c}]]]
}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
