source [file join [file dirname [info script]] json.tcl]
if {$argc!=2} {exit 2}
lassign $argv root output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set commands {}
foreach pattern {*DboTclHelper*Bit* *DboTclHelper*Dib* *DboTclHelper*DIB* *DboTclHelper*Image* *DboTclHelper*CSize* *charArray* *CharArray* *byteArray* *ByteArray*} {
 foreach command [info commands $pattern] {lappend commands $command}
}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj commands [cmcp::arr [lmap c [lsort -unique $commands] {cmcp::q $c}]]]} finally {close $f}
