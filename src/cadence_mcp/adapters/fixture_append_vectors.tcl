# Fixed typed graphic additions to a private OLB; no arbitrary methods/eval.
source [file join [file dirname [info script]] json.tcl]
package require json
if {$argc!=4} {exit 2}
lassign $argv root library request output
if {[file size $request]>65536} {exit 2}
set f [open $request];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
proc cmcp::pt {p} {return [DboTclHelper_sMakeCPoint {*}$p]}
set session "";set phase load
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 set package [$lib GetPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
 set device [$package GetDevice [cmcp::cs [dict get $spec designator]] $state];cmcp::check $state
 set cell [$device GetCell $state];cmcp::check $state
 foreach addition [dict get $spec additions] {
  set state [DboState];set it [$cell NewPartsIter $state];cmcp::check $state;set matches {}
  try {
   for {set part [$it NextPart $state]} {$part ne "NULL"} {set part [$it NextPart $state]} {
    cmcp::check $state;set name [cmcp::cs ""];cmcp::check [$part GetName $name]
    if {[cmcp::str $name] eq [dict get $addition partName]} {lappend matches $part}
   }
  } finally {delete_DboCellPartsIter $it}
  if {[llength $matches]!=1} {error ambiguous_source_part}
  set part [lindex $matches 0]
  foreach v [dict get $addition vectors] {
   set state [DboState];set kind [dict get $v kind];set phase "create_$kind"
   switch -- $kind {
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
     set font [DboTclHelper_sMakeLOGFONT {*}[dict get $v font]]
     set box [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]
     set obj [$part NewCommentText $state [cmcp::cs [dict get $v text]] $box [cmcp::pt [dict get $v location]] $font];cmcp::check $state
     cmcp::check [$obj SetBoundingBox [DboTclHelper_sMakeCRect {*}[dict get $v bounds]]]
    }
    default {error unsupported_fixture_kind}
   }
   if {$obj eq "NULL"} {error missing_vector}
  }
 }
 set phase save;cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
 set result [cmcp::obj saved true]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
