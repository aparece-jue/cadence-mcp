source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2}
lassign $argv root source identical different output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::getBitmap {session source} {
 set state [DboState];set lib [$session GetLibAndSchematics [cmcp::cs $source] $state];cmcp::check $state
 set pkg [$lib GetPackage [cmcp::cs MCP_DUALVAR] $state];cmcp::check $state
 set dev [$pkg GetDevice [cmcp::cs A] $state];cmcp::check $state
 set cell [$dev GetCell $state];cmcp::check $state
 set part [$cell GetPart [cmcp::cs GATE.Normal] $state];cmcp::check $state
 set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state;set matches {}
 try {for {set v [$it NextVector $state]} {$v ne "NULL"} {set v [$it NextVector $state]} {cmcp::check $state;if {[$v GetObjectType]==$::DboBaseObject_BITMAP_VECT} {lappend matches $v}}} finally {delete_DboGraphicObjectVectorsIter $it}
 if {[llength $matches]!=1} {error ambiguous_bitmap}
 return [list $lib $part [lindex $matches 0]]
}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
lassign [cmcp::getBitmap $session $source] la pa a
lassign [cmcp::getBitmap $session $identical] lb pb b
lassign [cmcp::getBitmap $session $different] lc pc c
if {$la eq $lb || $la eq $lc || $lb eq $lc || $a eq $b || $a eq $c} {error unexpectedly_shared_library_objects}
set aa [$a IsEquivalent $a];set ab [$a IsEquivalent $b];set ac [$a IsEquivalent $c]
set ba [$b IsEquivalent $a];set ca [$c IsEquivalent $a]
set ids {};foreach v [list $a $b $c] {set state [DboState];set id [$v GetId $state];if {[$state Failed]} {lappend ids [cmcp::obj supported false stateCode [$state Code]]} else {lappend ids [cmcp::obj supported true value $id]}}
set result [cmcp::obj self $aa identical $ab differentPixels $ac reverseIdentical $ba reverseDifferent $ca bitmapIds [cmcp::arr $ids] partIdentical [$pa IsEquivalent $pb] partDifferent [$pa IsEquivalent $pc]]
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}

