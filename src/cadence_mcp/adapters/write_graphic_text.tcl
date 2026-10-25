# Fixed page text addition; definition coordinates carry page placement, not instance SetLocation.
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
if {$argc!=4} {exit 2};lassign $argv root design specPath output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set rc [catch {
 if {[file size $specPath]>32768} {error spec_limit}
 set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 32769]]} finally {close $f}
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 if {$d eq "NULL"} {error missing_design}
 lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] sch page
 set operation add;if {[dict exists $spec operation]} {set operation [dict get $spec operation]}
 if {$operation ni {add update delete}} {error invalid_operation}
 set obj "NULL"
 if {$operation ne "add"} {
  set targetIndex [dict get $spec targetIndex];set expectedId [dict get $spec targetNativeId]
  set st [DboState];set it [$page NewCommentGraphicsIter $st];cmcp::check $st;set index 0
  try {
   while {1} {
    set st [DboState];set candidate [$it NextCommentGraphic $st]
    if {$candidate eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error iterator_end_error};break}
    cmcp::check $st
    if {$index>4096} {error graphic_limit}
    if {$index==$targetIndex} {
     set idState [DboState];set actualId [$candidate GetId $idState];cmcp::check $idState
     if {$actualId!=$expectedId || [$candidate GetObjectType]!=$::DboBaseObject_GRAPHIC_COMMENTTEXT_INST} {error target_identity_changed}
     set obj [DboGraphicInstanceToDboGraphicCommentTextInst $candidate];break
    }
    incr index
   }
  } finally {delete_DboPageCommentGraphicsIter $it}
  if {$obj eq "NULL"} {error missing_target_text}
 }
 if {$operation eq "delete"} {
  cmcp::check [$page DeleteCommentGraphic $obj]
 } else {
  set added [dict get $spec added];set v [dict get $added localDescriptor]
  set rect [DboTclHelper_sMakeCRect {*}[lindex $v 3]];set point [DboTclHelper_sMakeCPoint {*}[lindex $v 2]]
  set font [DboTclHelper_sMakeLOGFONT {*}[lindex $v 4]];set st [DboState]
  if {$operation eq "add"} {
   set obj [$page NewGraphicCommentTextInst $st $rect [DboTclHelper_sMakeCPoint 0 0] [cmcp::cs [lindex $v 1]] $font [dict get $added rotationCode]];cmcp::check $st
  }
  if {$obj eq "NULL"} {error missing_text}
  set raw [$obj GetDboCommentText];if {$raw eq "NULL"} {error missing_definition}
  cmcp::check [$raw SetText [cmcp::cs [lindex $v 1]]];cmcp::check [$raw SetFont $font]
  cmcp::check [$raw SetBoundingBox $rect];cmcp::check [$raw SetLocation $point]
  cmcp::check [$obj SetRotation [dict get $added rotationCode]];cmcp::check [$obj SetMirror [dict get $added mirrorCode]]
 }
 cmcp::check [$page MarkModified];cmcp::check [$sch MarkModified $page];cmcp::check [$sch SavePage $page];cmcp::check [$d SaveSchematic $sch];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;if {$rc} {puts $f [cmcp::obj saved false error [cmcp::q $message]]} else {puts $f [cmcp::obj saved true operation [cmcp::q "${operation}_graphic_text"]]}} finally {close $f}
if {$rc} {exit 1}
