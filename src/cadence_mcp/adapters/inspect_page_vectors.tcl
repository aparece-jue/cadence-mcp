# Fixed typed page-comment geometry reader, run through the installed embedded Tcl worker.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
source [file join [file dirname [info script]] dbo_vector_json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::shapePoint {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}
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
lassign $argv install design output schematicName pageName
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 lassign [cmcp::qualifiedPage $d $schematicName $pageName] sch page
 set it [$page NewCommentGraphicsIter $st];cmcp::check $st;set rows {};set n 0;set pointCount 0;set textCount 0
 try {
  for {set obj [$it NextCommentGraphic $st]} {$obj ne "NULL"} {set obj [$it NextCommentGraphic $st]} {
   cmcp::check $st;if {[incr n]>4096} {error graphic_limit}
   set id [$obj GetId $st];cmcp::check $st;set type [$obj GetObjectType];set location [$obj GetLocation $st];cmcp::check $st;set rotation [$obj GetRotation $st];cmcp::check $st;set mirror [$obj GetMirror $st];cmcp::check $st
   set descriptor null;set points {};set kind unsupported
   foreach {constant cast getter} {
    GRAPHIC_LINE_INST DboGraphicInstanceToDboGraphicLineInst GetDboLine
    GRAPHIC_BOX_INST DboGraphicInstanceToDboGraphicBoxInst GetDboBox
    GRAPHIC_ELLIPSE_INST DboGraphicInstanceToDboGraphicEllipseInst GetDboEllipse
    GRAPHIC_ARC_INST DboGraphicInstanceToDboGraphicArcInst GetDboArc
    GRAPHIC_POLYGON_INST DboGraphicInstanceToDboGraphicPolygonInst GetDboPolygon
    GRAPHIC_POLYLINE_INST DboGraphicInstanceToDboGraphicPolylineInst GetDboPolyline
    GRAPHIC_BEZIER_INST DboGraphicInstanceToDboGraphicBezierInst GetDboBezier
    GRAPHIC_COMMENTTEXT_INST DboGraphicInstanceToDboGraphicCommentTextInst GetDboCommentText
    GRAPHIC_BITMAP_INST DboGraphicInstanceToDboGraphicBitMapInst GetDboBitMap
   } {
    if {![info exists ::DboBaseObject_$constant]} {continue}
    if {$type!=[set ::DboBaseObject_$constant]} {continue}
    set typed [$cast $obj];set raw [$typed $getter];if {$raw eq "NULL"} {error missing_vector_definition}
    set value [cmcp::vectorDescriptor $raw];set kind [lindex $value 0];set descriptor [cmcp::descriptorJson $value]
    set localPoints [cmcp::controlPoints $value];incr pointCount [llength $localPoints];if {$pointCount>65536} {error point_budget}
    if {$kind eq "text"} {incr textCount [string length [lindex $value 1]];if {$textCount>262144} {error text_budget}}
    foreach p $localPoints {lappend points [cmcp::arr [cmcp::shapePoint [$obj GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}$p]]]]}
    break
   }
   lappend rows [cmcp::obj index [expr {$n-1}] nativeId $id nativeTypeCode $type kind [cmcp::q $kind] location [cmcp::arr [cmcp::shapePoint $location]] rotationCode $rotation mirrorCode $mirror localDescriptor $descriptor pageControlPoints [cmcp::arr $points]]
  }
 } finally {delete_DboPageCommentGraphicsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_graphics_iterator_end}
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: page vector read failed: $message";exit 1}
