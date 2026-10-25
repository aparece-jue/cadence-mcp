source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root target output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
proc cmcp::cs {s} {DboTclHelper_sMakeCString $s}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session CreateLib [cmcp::cs $target] $state];cmcp::check $state
set rows {};set i 0
foreach quality {0 1 2 3 4 5 6} {
 incr i
 set part [$lib NewPart [cmcp::cs "Q$quality.Normal"] $state];cmcp::check $state
 set package [$lib NewPackage [cmcp::cs "Q$quality"] $state];cmcp::check $state
 cmcp::check [$package SetReferenceTemplate [cmcp::cs "U?"]]
 set cell [$lib NewCell [cmcp::cs "Q$quality"] $state];cmcp::check $state
 cmcp::check [$cell AddPart $part]
 set device [$package NewDevice [cmcp::cs A] 0 $cell $state];cmcp::check $state
 set font [DboTclHelper_sMakeLOGFONT Arial 8 1 0 0 500 0 0 1 1 3 1 $quality 32]
 set constructed [DboTclHelper_sGetLFQuality $font]
 set id [$lib SetFont $font]
 set box [DboTclHelper_sMakeCRect 0 0 100 20]
 set text [$part NewCommentText $state [cmcp::cs "Quality $quality"] $box [DboTclHelper_sMakeCPoint 0 0] $font];cmcp::check $state
 set actual [$text GetFont $state];cmcp::check $state;set created [DboTclHelper_sGetLFQuality $actual]
 cmcp::check [$text SetBoundingBox $box]
 set actual [$text GetFont $state];cmcp::check $state;set bounded [DboTclHelper_sGetLFQuality $actual]
 set actualId [$text GetFontId]
 set default [$text IsFontDefault $state];cmcp::check $state
 lappend rows [cmcp::obj requested $quality constructed $constructed registeredId $id created $created afterBounds $bounded actualId $actualId isDefault $default]
}
cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
