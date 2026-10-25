source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root target output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
proc cmcp::cs {s} {DboTclHelper_sMakeCString $s}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session GetLibAndSchematics [cmcp::cs $target] $state];cmcp::check $state
set rows {}
foreach quality {0 1 2 3 4 5 6} {
 set package [$lib GetPackage [cmcp::cs "Q$quality"] $state];cmcp::check $state
 set device [$package GetDevice [cmcp::cs A] $state];cmcp::check $state
 set cell [$device GetCell $state];cmcp::check $state
 set part [$cell GetPart [cmcp::cs "Q$quality.Normal"] $state];cmcp::check $state
 set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state
 try {set v [$it NextVector $state];cmcp::check $state;set obj [DboVectorToDboCommentText $v];set font [$obj GetFont $state];cmcp::check $state;set actual [DboTclHelper_sGetLFQuality $font]} finally {delete_DboGraphicObjectVectorsIter $it}
 lappend rows [cmcp::obj requested $quality reopened $actual]
}
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
