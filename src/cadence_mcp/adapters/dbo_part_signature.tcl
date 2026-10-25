# Bounded source/cache identity for pins and basic typed vectors. Legacy line-only signature retained.
# Unsupported vector kinds fail rather than silently losing graphical identity.
proc cmcp::shapePoint {p} {return [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]}
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
proc cmcp::partShapeSignature {part} {
    set state [DboState];set pins {};set lines {};set count 0
    set it [$part NewLPinsIter $state];cmcp::check $state
    try {
        for {set pin [$it NextPin $state]} {$pin ne "NULL"} {set pin [$it NextPin $state]} {
            cmcp::check $state
            if {[incr count]>512} {error signature_pin_limit}
            set name [cmcp::cs ""];cmcp::check [$pin GetPinName $name]
            set position [$pin GetPinPosition $state];cmcp::check $state
            set type [$pin GetPinType $state];cmcp::check $state
            set visible [$pin GetIsVisible $state];cmcp::check $state
            set start [$pin GetStartPoint $state];cmcp::check $state
            set hot [$pin GetHotSpot $state];cmcp::check $state
            lappend pins [list $position [cmcp::str $name] $type $visible [cmcp::shapePoint $start] [cmcp::shapePoint $hot]]
        }
        if {[$state Failed] && [$state Code]!=1022} {error signature_pin_iterator_end}
    } finally {delete_DboLibPartPinsIter $it}
    set state [DboState];set count 0;set vectors {};set onlyLines 1;set totalPoints 0;set totalText 0
    set it [$part NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state
    try {
        for {set vector [$it NextVector $state]} {$vector ne "NULL"} {set vector [$it NextVector $state]} {
            cmcp::check $state
            if {[incr count]>4096} {error signature_vector_limit}
            set descriptor [cmcp::vectorDescriptor $vector]
            set kind [lindex $descriptor 0]
            if {$kind in {polygon polyline bezier}} {incr totalPoints [llength [lindex $descriptor 1]]} else {incr totalPoints 4}
            if {$kind eq "text"} {incr totalText [string length [lindex $descriptor 1]]}
            if {$totalPoints>65536 || $totalText>262144} {error signature_geometry_budget}
            lappend vectors $descriptor
            if {[lindex $descriptor 0] eq "line"} {lappend lines [lrange $descriptor 1 end]} else {set onlyLines 0}
        }
        if {[$state Failed] && [$state Code]!=1022} {error signature_vector_iterator_end}
    } finally {delete_DboGraphicObjectVectorsIter $it}
    if {$onlyLines} {return [list [lsort $pins] [lsort $lines]]}
    return [list [lsort $pins] [list ordered_vectors $vectors]]
}

