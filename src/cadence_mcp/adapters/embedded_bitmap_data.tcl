# Fixed same-process DIB read; retain the session until Python copies the global block.
source [file join [file dirname [info script]] json.tcl]
lassign $argv root library
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set ::cmcp::bitmapSession [DboTclHelper_sCreateSession];set state [DboState]
set lib [$::cmcp::bitmapSession GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
set pkg [$lib GetPackage [cmcp::cs MCP_DUALVAR] $state];cmcp::check $state
set dev [$pkg GetDevice [cmcp::cs A] $state];cmcp::check $state
set cell [$dev GetCell $state];cmcp::check $state
set part [$cell GetPart [cmcp::cs GATE.Normal] $state];cmcp::check $state
set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state;set objects {}
try {for {set v [$it NextVector $state]} {$v ne "NULL"} {set v [$it NextVector $state]} {cmcp::check $state;if {[$v GetObjectType]==$::DboBaseObject_BITMAP_VECT} {lappend objects $v}}} finally {delete_DboGraphicObjectVectorsIter $it}
if {[llength $objects]!=1} {error ambiguous_bitmap}
set bitmap [DboVectorToDboBitMap [lindex $objects 0]];set state [DboState]
set size [$bitmap GetDibSize $state];cmcp::check $state
if {$size<=0 || $size>16777216} {error dib_size_limit}
set handle [$bitmap GetDib $state];cmcp::check $state
proc cmcp::closeBitmapData {} {if {[info exists ::cmcp::bitmapSession]} {delete_DboSession $::cmcp::bitmapSession;unset ::cmcp::bitmapSession}}
cmcp::obj dibSize $size dibHandle [cmcp::q $handle]
