source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2}
lassign $argv root library bitmap output mode
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::point {p} {cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]}
set session "";set phase open
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 set package [$lib GetPackage [cmcp::cs MCP_DUALVAR] $state];cmcp::check $state
 set device [$package GetDevice [cmcp::cs A] $state];cmcp::check $state
 set cell [$device GetCell $state];cmcp::check $state
 set part [$cell GetPart [cmcp::cs GATE.Normal] $state];cmcp::check $state
 if {$mode in {create create_shifted}} {
  if {$mode eq "create_shifted"} {set dummy [$part NewLine $state [DboTclHelper_sMakeCPoint 101 101] [DboTclHelper_sMakeCPoint 102 102] 0 0];cmcp::check $state}
  set phase make_bitmap_data
  set data [DboTclHelper_sMakeBitMapData [DboTclHelper_sMakeCRect 0 0 20 20] [DboTclHelper_sMakeCPoint 0 0] $bitmap]
  set phase make_bitmap
  set created [DboTclHelper_sMakeBitmap $data $part NULL 0 $state];cmcp::check $state
  if {$mode eq "create_shifted"} {cmcp::check [$part DeleteVector $dummy]}
  set phase save;cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
 }
 set phase inspect;set names {};foreach name [info vars ::DboBaseObject_*] {if {[string match *BIT* $name]} {lappend names [cmcp::obj name [cmcp::q $name] value [set $name]]}}
 set rows {};set count 0;set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state
 try {
  for {set vector [$it NextVector $state]} {$vector ne "NULL"} {set vector [$it NextVector $state]} {
   cmcp::check $state;incr count
   if {[$vector GetObjectType]!=$::DboBaseObject_BITMAP_VECT} {continue}
   set object [DboVectorToDboBitMap $vector]
   set box [$object GetBoundingBox];set point [$object GetLocation $state];cmcp::check $state
   set dimensions [$object GetBitmapDimension $state];cmcp::check $state
   set size [$object GetDibSize $state];cmcp::check $state
   lappend rows [cmcp::obj index [expr {$count-1}] bounds [cmcp::arr [list [DboTclHelper_sGetCPointX [DboTclHelper_sGetCRectTopLeft $box]] [DboTclHelper_sGetCPointY [DboTclHelper_sGetCRectTopLeft $box]] [DboTclHelper_sGetCPointX [DboTclHelper_sGetCRectBottomRight $box]] [DboTclHelper_sGetCPointY [DboTclHelper_sGetCRectBottomRight $box]]]] location [cmcp::point $point] dimensions [cmcp::arr [list [DboTclHelper_sGetCSizeX $dimensions] [DboTclHelper_sGetCSizeY $dimensions]]] dibSize $size]
  }
 } finally {delete_DboGraphicObjectVectorsIter $it}
 set result [cmcp::obj succeeded true mode [cmcp::q $mode] vectorCount $count bitmaps [cmcp::arr $rows] constants [cmcp::arr $names]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj succeeded false mode [cmcp::q $mode] phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}

