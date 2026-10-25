# Read-only registry/constant probe for the configured local Dbo runtime.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=2} {exit 2}
lassign $argv root output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set commands [lsort [concat [info commands DboTclHelper_sGetLF*] [info commands *PointsIter*]]]
set constants {}
foreach name [lsort [info globals DboBaseObject_*]] {
 if {[regexp {_(BOX|ARC|ELLIPSE|POLYGON|POLYLINE|BEZIER|COMMENTTEXT|COMMENT_TEXT|FILL|TEXT)$} $name]} {lappend constants [cmcp::obj name [cmcp::q $name] value [set ::$name]]}
}
foreach name [lsort [info globals DboValue_*]] {if {[regexp {(FILL|HATCH|LINE|WIDTH)} $name]} {lappend constants [cmcp::obj name [cmcp::q $name] value [set ::$name]]}}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj commands [cmcp::arr [lmap name $commands {cmcp::q $name}]] constants [cmcp::arr $constants]]} finally {close $f}

