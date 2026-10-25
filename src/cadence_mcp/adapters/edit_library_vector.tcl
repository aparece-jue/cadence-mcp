# Fixed in-place property edits on one bound vector in a new private OLB copy.
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_part_signature.tcl]
source [file join [file dirname [info script]] dbo_vector_json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root library request output
if {[file size $request]>65536} {exit 2}
set f [open $request];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
proc cmcp::pt {p} {DboTclHelper_sMakeCPoint {*}$p}
proc cmcp::setDeclaredVector {vector v} {
 set kind [dict get $v kind]
 switch -- $kind {
  bitmap {
   set obj [DboVectorToDboBitMap $vector]
   cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]]
   cmcp::check [$obj SetLocation [cmcp::pt [dict get $v location]]]
  }
  line {set obj [DboVectorToDboLine $vector];cmcp::check [$obj SetStart [cmcp::pt [dict get $v start]]];cmcp::check [$obj SetEnd [cmcp::pt [dict get $v end]]]}
  box {set obj [DboVectorToDboBox $vector];cmcp::check [$obj SetUpperLeft [cmcp::pt [lrange [dict get $v bounds] 0 1]]];cmcp::check [$obj SetLowerRight [cmcp::pt [lrange [dict get $v bounds] 2 3]]]}
  ellipse {set obj [DboVectorToDboEllipse $vector];cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]]}
  arc {set obj [DboVectorToDboArc $vector];cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]];cmcp::check [$obj SetStart [cmcp::pt [dict get $v start]]];cmcp::check [$obj SetEnd [cmcp::pt [dict get $v end]]]}
  polygon - polyline - bezier {
   if {$kind eq "polygon"} {set obj [DboVectorToDboPolygon $vector]} elseif {$kind eq "polyline"} {set obj [DboVectorToDboPolyline $vector]} else {set obj [DboVectorToDboBezier $vector]}
   cmcp::check [$obj RemoveAllPoints]
   foreach point [dict get $v points] {cmcp::check [$obj NewPoint [cmcp::pt $point]]}
  }
  fill {set obj [DboVectorToDboFill $vector];cmcp::check [$obj SetStart [cmcp::pt [dict get $v start]]]}
  text {
   set obj [DboVectorToDboCommentText $vector]
   cmcp::check [$obj SetText [cmcp::cs [dict get $v text]]]
   set fields {};foreach key {faceName height width escapement orientation weight italic underline strikeOut charSet outPrecision clipPrecision quality pitchAndFamily} {
    set value [dict get $v font $key];if {$key in {italic underline strikeOut}} {set value [expr {$value ? 1 : 0}]};lappend fields $value
   }
   cmcp::check [$obj SetFont [DboTclHelper_sMakeLOGFONT {*}$fields]]
   cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]]
  }
  default {error unsupported_declared_vector_kind}
 }
 if {$kind in {line box ellipse arc polygon polyline bezier}} {cmcp::check [$obj SetLineStyle [dict get $v style]];cmcp::check [$obj SetLineWidth [dict get $v width]]}
 if {$kind in {box ellipse polygon fill}} {cmcp::check [$obj SetFillStyle [dict get $v fill]];cmcp::check [$obj SetHatchStyle [dict get $v hatch]]}
}
set session "";set phase open
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 lassign [dict get $spec scope] packageName designator position cellName partName
 set declaredScopes [dict get $spec affectedScopes];set seenScopes {};set chosenObjects {};set count 0
 set packages [$lib NewPackagesIter $state];cmcp::check $state
 try {
  for {set pkg [$packages NextPackage $state]} {$pkg ne "NULL"} {set pkg [$packages NextPackage $state]} {
   cmcp::check $state;set pkgname [cmcp::cs ""];cmcp::check [$pkg GetName $pkgname]
   set devices [$pkg NewDevicesIter $state];cmcp::check $state
   try {
    for {set device [$devices NextDevice $state]} {$device ne "NULL"} {set device [$devices NextDevice $state]} {
     cmcp::check $state;set devname [cmcp::cs ""];cmcp::check [$device GetDesignator $devname]
     set devpos [$device GetPosition $state];cmcp::check $state
     set cellname [cmcp::cs ""];cmcp::check [$device GetCellName $cellname]
     set cell [$device GetCell $state];cmcp::check $state
     set parts [$cell NewPartsIter $state];cmcp::check $state
     try {
      for {set part [$parts NextPart $state]} {$part ne "NULL"} {set part [$parts NextPart $state]} {
       cmcp::check $state;if {[incr count]>100000} {error view_limit}
       set name [cmcp::cs ""];cmcp::check [$part GetName $name]
       if {[cmcp::str $name] ne $partName} {continue}
       set actualScope [list [cmcp::str $pkgname] [cmcp::str $devname] $devpos [cmcp::str $cellname] [cmcp::str $name]]
       if {[lsearch -exact $declaredScopes $actualScope]<0 || [dict exists $seenScopes $actualScope]} {error unexpected_reference_scope}
       dict set seenScopes $actualScope 1
       set vs [DboState];set it [$part NewVectorsIter $vs $::IterDefs_ALL];cmcp::check $vs
       set chosen "";set index 0
       try {
        for {set vector [$it NextVector $vs]} {$vector ne "NULL"} {set vector [$it NextVector $vs]} {
         cmcp::check $vs;if {$index==[dict get $spec index]} {set chosen $vector}
         if {[incr index]>4096} {error vector_limit}
        }
       } finally {delete_DboGraphicObjectVectorsIter $it}
       if {[$vs Failed] && [$vs Code]!=1022} {error unexpected_vector_iterator_end}
       if {$chosen eq ""} {error missing_bound_vector}
       set phase validate_old
       if {[cmcp::descriptorJson [cmcp::vectorDescriptor $chosen]] ne [cmcp::descriptorJson [dict get $spec old]]} {error old_vector_mismatch}
       dict set chosenObjects $chosen [list $part $chosen]
      }
     } finally {delete_DboCellPartsIter $parts}
    }
   } finally {delete_DboPackageDevicesIter $devices}
  }
 } finally {delete_DboLibPackagesIter $packages}
 if {[dict size $seenScopes]!=[llength $declaredScopes] || ![dict exists $seenScopes [dict get $spec scope]]} {error missing_reference_scopes}
 set phase [dict get $spec operation]
 # All reference contexts are checked before touching any native object.
 dict for {pointer pair} $chosenObjects {
  lassign $pair part chosen
  if {$phase eq "delete"} {cmcp::check [$part DeleteVector $chosen]} elseif {$phase eq "update"} {
   if {[dict get $spec replacement kind] ne [lindex [dict get $spec old] 0]} {error vector_kind_change}
   cmcp::setDeclaredVector $chosen [dict get $spec replacement]
  } else {error invalid_vector_edit_operation}
 }
 set phase save;cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
 set result [cmcp::obj saved true vectorId [cmcp::q [dict get $spec vectorId]]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: vector edit failed at $phase: $message";exit 1}
