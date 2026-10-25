# Typed geometry/style descriptors. Preserve point order and native vector draw order.
proc cmcp::vectorRect {r} {return [concat [cmcp::shapePoint [DboTclHelper_sGetCRectTopLeft $r]] [cmcp::shapePoint [DboTclHelper_sGetCRectBottomRight $r]]]}
proc cmcp::vectorFont {font} {
    set face [cmcp::cs ""]
    DboTclHelper_sGetLFName $font $face
    return [list [cmcp::str $face] [DboTclHelper_sGetLFHeight $font] [DboTclHelper_sGetLFWidth $font] [DboTclHelper_sGetLFEscapement $font] [DboTclHelper_sGetLFOrientation $font] [DboTclHelper_sGetLFWeight $font] [DboTclHelper_sGetLFItalic $font] [DboTclHelper_sGetLFUnderline $font] [DboTclHelper_sGetLFStrikeOut $font] [DboTclHelper_sGetLFCharSet $font] [DboTclHelper_sGetLFOutPrecision $font] [DboTclHelper_sGetLFClipPrecision $font] [DboTclHelper_sGetLFQuality $font] [DboTclHelper_sGetLFPitchAndFamily $font]]
}
proc cmcp::vectorDescriptor {vector} {
    set type [$vector GetObjectType];set state [DboState]
    if {$type==$::DboBaseObject_BITMAP_VECT} {
        if {[info commands ::cmcp::bitmapDigest] eq ""} {error bitmap_byte_worker_required}
        set obj [DboVectorToDboBitMap $vector]
        set bounds [cmcp::vectorRect [$obj GetBoundingBox]]
        set location [$obj GetLocation $state];cmcp::check $state
        set dimension [$obj GetBitmapDimension $state];cmcp::check $state
        set size [$obj GetDibSize $state];cmcp::check $state
        set handle [$obj GetDib $state];cmcp::check $state
        set digest [cmcp::bitmapDigest $handle $size]
        return [list bitmap $bounds [cmcp::shapePoint $location] [list [DboTclHelper_sGetCSizeX $dimension] [DboTclHelper_sGetCSizeY $dimension]] $size $digest]
    }
    if {$type==$::DboBaseObject_LINE} {
        set obj [DboVectorToDboLine $vector];set start [$obj GetStart $state];cmcp::check $state;set end [$obj GetEnd $state];cmcp::check $state
        set style [$obj GetLineStyle $state];cmcp::check $state;set width [$obj GetLineWidth $state];cmcp::check $state
        return [list line [cmcp::shapePoint $start] [cmcp::shapePoint $end] $style $width]
    }
    if {$type==$::DboBaseObject_BOX} {
        set obj [DboVectorToDboBox $vector];set left [$obj GetUpperLeft $state];cmcp::check $state;set right [$obj GetLowerRight $state];cmcp::check $state
        set bounds [concat [cmcp::shapePoint $left] [cmcp::shapePoint $right]];set kind box
    } elseif {$type==$::DboBaseObject_ELLIPSE} {
        set obj [DboVectorToDboEllipse $vector];set bounds [cmcp::vectorRect [$obj GetBoundingBox]];set kind ellipse
    } elseif {$type==$::DboBaseObject_ARC} {
        set obj [DboVectorToDboArc $vector];set bounds [cmcp::vectorRect [$obj GetBoundingBox]]
        set start [$obj GetStart $state];cmcp::check $state;set end [$obj GetEnd $state];cmcp::check $state
        set style [$obj GetLineStyle $state];cmcp::check $state;set width [$obj GetLineWidth $state];cmcp::check $state
        return [list arc $bounds [cmcp::shapePoint $start] [cmcp::shapePoint $end] $style $width]
    } elseif {$type==$::DboBaseObject_COMMENT_TEXT} {
        set obj [DboVectorToDboCommentText $vector];set text [cmcp::cs ""];cmcp::check [$obj GetText $text]
        if {[string length [cmcp::str $text]]>65536} {error signature_text_limit}
        set point [$obj GetLocation $state];cmcp::check $state;set font [$obj GetFont $state];cmcp::check $state
        set default [$obj IsFontDefault $state];cmcp::check $state
        return [list text [cmcp::str $text] [cmcp::shapePoint $point] [cmcp::vectorRect [$obj GetBoundingBox]] [cmcp::vectorFont $font] $default]
    } elseif {$type==$::DboBaseObject_FILL} {
        set obj [DboVectorToDboFill $vector];set start [$obj GetStart $state];cmcp::check $state
        set fill [$obj GetFillStyle $state];cmcp::check $state;set hatch [$obj GetHatchStyle $state];cmcp::check $state
        return [list fill [cmcp::shapePoint $start] $fill $hatch]
    } elseif {$type==$::DboBaseObject_POLYGON || $type==$::DboBaseObject_POLYLINE || $type==$::DboBaseObject_BEZIER} {
        if {$type==$::DboBaseObject_POLYGON} {set obj [DboVectorToDboPolygon $vector];set kind polygon;set dispose delete_DboPolygonPointsIter} elseif {$type==$::DboBaseObject_POLYLINE} {set obj [DboVectorToDboPolyline $vector];set kind polyline;set dispose delete_DboPolylinePointsIter} else {set obj [DboVectorToDboBezier $vector];set kind bezier;set dispose delete_DboBezierPointsIter}
        set n [$obj GetCount $state];cmcp::check $state
        if {$n<0 || $n>4096} {error signature_point_limit}
        set it [$obj NewPointsIter $state];cmcp::check $state;set points {};set p [DboTclHelper_sMakeCPoint 0 0]
        try {for {set i 0} {$i<$n} {incr i} {$it Next $p;lappend points [cmcp::shapePoint $p]}} finally {$dispose $it}
        set style [$obj GetLineStyle $state];cmcp::check $state;set width [$obj GetLineWidth $state];cmcp::check $state
        if {$kind eq "polygon"} {set fill [$obj GetFillStyle $state];cmcp::check $state;set hatch [$obj GetHatchStyle $state];cmcp::check $state;return [list polygon $points $style $width $fill $hatch]}
        return [list $kind $points $style $width]
    } else {error "unsupported_variant_vector_$type"}
    set style [$obj GetLineStyle $state];cmcp::check $state;set width [$obj GetLineWidth $state];cmcp::check $state
    set fill [$obj GetFillStyle $state];cmcp::check $state;set hatch [$obj GetHatchStyle $state];cmcp::check $state
    return [list $kind $bounds $style $width $fill $hatch]
}

