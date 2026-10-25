namespace eval cmcp {}
proc cmcp::createDeclaredVector {part v} {
 set state [DboState];set kind [dict get $v kind]
   switch -- $kind {
    bitmap {
     set data [DboTclHelper_sMakeBitMapData [DboTclHelper_sMakeCRect {*}[dict get $v bounds]] [cmcp::pt [dict get $v location]] [dict get $v sourceBmp]]
     set obj [DboTclHelper_sMakeBitmap $data $part NULL 0 $state];cmcp::check $state
    }
    line {set obj [$part NewLine $state [cmcp::pt [dict get $v start]] [cmcp::pt [dict get $v end]] [dict get $v style] [dict get $v width]];cmcp::check $state}
    box {set obj [$part NewBox $state [cmcp::pt [lrange [dict get $v bounds] 0 1]] [cmcp::pt [lrange [dict get $v bounds] 2 3]] [dict get $v style] [dict get $v width] [dict get $v fill] [dict get $v hatch]];cmcp::check $state}
    ellipse {set obj [$part NewEllipse $state [DboTclHelper_sMakeCRect {*}[dict get $v bounds]] [dict get $v style] [dict get $v width] [dict get $v fill] [dict get $v hatch]];cmcp::check $state}
    arc {set obj [$part NewArc $state [DboTclHelper_sMakeCRect {*}[dict get $v bounds]] [cmcp::pt [dict get $v start]] [cmcp::pt [dict get $v end]] [dict get $v style] [dict get $v width]];cmcp::check $state}
    polygon - polyline - bezier {
     if {$kind eq "polygon"} {set obj [$part NewPolygon $state [dict get $v style] [dict get $v width] [dict get $v fill] [dict get $v hatch]]} elseif {$kind eq "polyline"} {set obj [$part NewPolyline $state [dict get $v style] [dict get $v width]]} else {set obj [$part NewBezier $state [dict get $v style] [dict get $v width]]}
     cmcp::check $state
     foreach p [dict get $v points] {cmcp::check [$obj NewPoint [cmcp::pt $p]]}
    }
    fill {set obj [$part NewFill $state [cmcp::pt [dict get $v start]] [dict get $v fill] [dict get $v hatch]];cmcp::check $state}
    text {
     set fields {};foreach key {faceName height width escapement orientation weight italic underline strikeOut charSet outPrecision clipPrecision quality pitchAndFamily} {set value [dict get $v font $key];if {$key in {italic underline strikeOut}} {set value [expr {$value ? 1 : 0}]};lappend fields $value}
     set font [DboTclHelper_sMakeLOGFONT {*}$fields]
     set box [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]
     set obj [$part NewCommentText $state [cmcp::cs [dict get $v text]] $box [cmcp::pt [lrange [dict get $v bounds] 0 1]] $font];cmcp::check $state
     cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]]
    }
    default {error unsupported_declared_vector_kind}
   }
 if {$obj eq "NULL"} {error missing_vector}
 return $obj
}
