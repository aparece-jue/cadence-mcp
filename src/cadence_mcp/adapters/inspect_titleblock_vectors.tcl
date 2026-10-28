# Fixed bounded titleblock definition reader; no mutation or GUI.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
source [file join [file dirname [info script]] dbo_vector_json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::corners {r} {lassign $r x1 y1 x2 y2;list [list $x1 $y1] [list $x2 $y1] [list $x2 $y2] [list $x1 $y2]}
proc cmcp::controlPoints {v} {
 switch -- [lindex $v 0] {
  line {return [list [lindex $v 1] [lindex $v 2]]}
  box - ellipse {return [cmcp::corners [lindex $v 1]]}
  arc {return [concat [cmcp::corners [lindex $v 1]] [list [lindex $v 2] [lindex $v 3]]]}
  polygon - polyline - bezier {return [lindex $v 1]}
  text {return [concat [list [lindex $v 2]] [cmcp::corners [lindex $v 3]]]}
  bitmap {return [concat [list [lindex $v 2]] [cmcp::corners [lindex $v 1]]]}
  default {error unsupported_control_points}
 }
}
proc cmcp::shapePoint {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}

if {$argc!=6} {exit 2}
lassign $argv install design output schematicName pageName nativeId
if {![string is integer -strict $nativeId] || $nativeId<0 || $nativeId>4294967295} {exit 2}
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 lassign [cmcp::qualifiedPage $d $schematicName $pageName] s p
 set it [$p NewTitleBlocksIter $st];cmcp::check $st;set matches {};set n 0
 try {for {set obj [$it NextTitleBlock $st]} {$obj ne "NULL"} {set obj [$it NextTitleBlock $st]} {
  cmcp::check $st;if {[incr n]>4096} {error titleblock_limit}
  set id [$obj GetId $st];cmcp::check $st
  if {$id==$nativeId} {lappend matches $obj}
 }} finally {delete_DboPageTitleBlocksIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_titleblock_iterator_end}
 if {[llength $matches]!=1} {error ambiguous_titleblock};set obj [lindex $matches 0]
 set st [DboState];set name [cmcp::cs ""];cmcp::check [$obj GetName $name]
 set symbolName [cmcp::cs ""];cmcp::check [$obj GetSourceSymbolName $symbolName]
 set location [$obj GetLocation $st];cmcp::check $st;set rotation [$obj GetRotation $st];cmcp::check $st;set mirror [$obj GetMirror $st];cmcp::check $st
 set definition [$obj GetSymbol $st];cmcp::check $st;if {$definition eq "NULL"} {error missing_titleblock_symbol}
 set vs [DboState];set vectors [$definition NewVectorsIter $vs $::IterDefs_ALL];cmcp::check $vs
 set vectorRows {};set vectorCount 0;set pointCount 0;set textCount 0
 try {for {set vector [$vectors NextVector $vs]} {$vector ne "NULL"} {set vector [$vectors NextVector $vs]} {
  cmcp::check $vs;if {[incr vectorCount]>4096} {error vector_limit}
  set type [$vector GetObjectType];set descriptor null;set points {};set kind unsupported;set supported 0
  foreach constant {LINE BOX ELLIPSE ARC POLYGON POLYLINE BEZIER COMMENT_TEXT BITMAP_VECT} {
   if {[info exists ::DboBaseObject_$constant] && $type==[set ::DboBaseObject_$constant]} {set supported 1;break}
  }
  if {$supported} {
   set value [cmcp::vectorDescriptor $vector];set kind [lindex $value 0];set descriptor [cmcp::descriptorJson $value]
   set localPoints [cmcp::controlPoints $value];incr pointCount [llength $localPoints];if {$pointCount>65536} {error point_budget}
   if {$kind eq "text"} {incr textCount [string length [lindex $value 1]];if {$textCount>262144} {error text_budget}}
   foreach point $localPoints {lappend points [cmcp::arr [cmcp::shapePoint [$obj GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}$point]]]]}
  }
  lappend vectorRows [cmcp::obj index [expr {$vectorCount-1}] nativeId null nativeTypeCode $type kind [cmcp::q $kind] location [cmcp::arr [cmcp::shapePoint $location]] rotationCode $rotation mirrorCode $mirror localDescriptor $descriptor pageControlPoints [cmcp::arr $points]]
 }} finally {delete_DboGraphicObjectVectorsIter $vectors}
 if {[$vs Failed] && [$vs Code]!=1022} {error unexpected_vector_iterator_end}
 set result [cmcp::obj nativeId $nativeId name [cmcp::q [cmcp::str $name]] sourceSymbol [cmcp::q [cmcp::str $symbolName]] location [cmcp::arr [cmcp::shapePoint $location]] rotationCode $rotation mirrorCode $mirror vectors [cmcp::arr $vectorRows]]
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: titleblock vectors: $message";exit 1}
