source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root library output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
set pkg [$lib GetPackage [cmcp::cs MCP_DUALVAR] $state];cmcp::check $state
set device [$pkg GetDevice [cmcp::cs A] $state];cmcp::check $state
set cell [$device GetCell $state];cmcp::check $state
set part [$cell GetPart [cmcp::cs GATE.Normal] $state];cmcp::check $state
set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state;set rows {};set index 0
try {
 for {set v [$it NextVector $state]} {$v ne "NULL"} {set v [$it NextVector $state]} {
  cmcp::check $state;set name [cmcp::cs ""];cmcp::check [$v GetTypeString $name]
  lappend rows [cmcp::obj index $index typeCode [$v GetObjectType] typeName [cmcp::q [cmcp::str $name]]];incr index
 }
} finally {delete_DboGraphicObjectVectorsIter $it}
set enums {};foreach name [info vars ::DboBaseObject_*] {if {[string match *BIT* $name] || [string match *OLE* $name]} {lappend enums [cmcp::obj name [cmcp::q $name] value [set $name]]}}
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj vectors [cmcp::arr $rows] enums [cmcp::arr $enums]]} finally {close $f}
