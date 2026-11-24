# Fixed existing decorative-line mutation. No caller-supplied Tcl or method names.
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
if {$argc!=4} {exit 2};lassign $argv install design specPath output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::pointList {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}
proc cmcp::boundedPoint {p} {
 if {[llength $p]!=2} {error invalid_point}
 foreach n $p {if {![string is integer -strict $n] || $n < -1000000 || $n > 1000000} {error invalid_point}}
 return [DboTclHelper_sMakeCPoint {*}$p]
}
proc cmcp::snapshotLine {obj} {
 set st [DboState];set raw [$obj GetDboLine];if {$raw eq "NULL"} {error missing_line_definition}
 set owner [$raw GetOwner];if {$owner eq "NULL"} {error missing_line_owner}
 set result {}
 foreach {key method} {nativeId GetId rotationCode GetRotation mirrorCode GetMirror lineColor GetColor} {
  set v [$obj $method $st];cmcp::check $st;dict set result $key $v
 }
 foreach {key method} {localStart GetStart localEnd GetEnd} {
  set v [$raw $method $st];cmcp::check $st;dict set result $key [cmcp::pointList $v]
 }
 set v [$obj GetLocation $st];cmcp::check $st;dict set result location [cmcp::pointList $v]
 foreach {key method} {lineStyle GetLineStyle lineWidth GetLineWidth} {
  set v [$raw $method $st];cmcp::check $st;dict set result $key $v
 }
 set color [DboGraphicObject_sGetColor $owner $st];cmcp::check $st;dict set result definitionColor $color
 foreach {key local} {start localStart end localEnd} {
  dict set result $key [cmcp::pointList [$obj GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}[dict get $result $local]]]]
 }
 return $result
}
set session "";set rc [catch {
 if {[file size $specPath]>32768} {error spec_limit}
 set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 32769]]} finally {close $f}
 if {[lsort [dict keys $spec]] ne [lsort {schema operation schematicName pageName targetIndex targetNativeId oldLine change}] || [dict get $spec schema]!=1} {error invalid_spec}
 set operation [dict get $spec operation];set targetIndex [dict get $spec targetIndex];set expectedId [dict get $spec targetNativeId]
 if {$operation ni {update delete} || ![string is integer -strict $targetIndex] || $targetIndex<0 || $targetIndex>4095 || ![string is integer -strict $expectedId] || $expectedId<0 || $expectedId>4294967295} {error invalid_target}
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 if {$d eq "NULL"} {error missing_design}
 lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] sch page
 set st [DboState];set it [$page NewCommentGraphicsIter $st];cmcp::check $st;set index 0;set obj "NULL"
 try {
  while {1} {
   set st [DboState];set candidate [$it NextCommentGraphic $st]
   if {$candidate eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error bad_iterator_end};break}
   cmcp::check $st;if {$index>=4096} {error graphic_limit}
   if {$index==$targetIndex} {
    set id [$candidate GetId $st];cmcp::check $st
    if {$id!=$expectedId || [$candidate GetObjectType]!=$::DboBaseObject_GRAPHIC_LINE_INST} {error target_identity_changed}
    set obj [DboGraphicInstanceToDboGraphicLineInst $candidate];break
   }
   incr index
  }
 } finally {delete_DboPageCommentGraphicsIter $it}
 if {$obj eq "NULL"} {error missing_target_line}
 set old [dict get $spec oldLine];set actual [cmcp::snapshotLine $obj]
 if {[lsort [dict keys $old]] ne [lsort [dict keys $actual]]} {error old_line_shape}
 foreach key [dict keys $actual] {
  if {$key in {localStart localEnd location start end}} {
   if {[list {*}[dict get $old $key]] ne [list {*}[dict get $actual $key]]} {error old_line_changed}
  } elseif {[dict get $old $key] ne [dict get $actual $key]} {error old_line_changed}
 }
 if {$operation eq "delete"} {
  if {[dict get $spec change] ne "null"} {error delete_change_forbidden}
  cmcp::check [$page DeleteCommentGraphic $obj]
 } else {
  set change [dict get $spec change]
  if {[lsort [dict keys $change]] ne [lsort {localStart localEnd location rotation mirror lineStyle lineWidth lineColor}]} {error change_shape}
  foreach {key maximum minimum} {rotation 3 0 mirror 1 0 lineStyle 5 0 lineWidth 3 0 lineColor 48 1} {
   set v [dict get $change $key];if {![string is integer -strict $v] || $v<$minimum || $v>$maximum} {error change_range}
  }
  if {[dict get $change localStart] eq [dict get $change localEnd]} {error zero_line}
  set a [cmcp::boundedPoint [dict get $change localStart]];set b [cmcp::boundedPoint [dict get $change localEnd]];set location [cmcp::boundedPoint [dict get $change location]]
  set raw [$obj GetDboLine];set owner [$raw GetOwner]
  cmcp::check [$raw SetStart $a];cmcp::check [$raw SetEnd $b]
  cmcp::check [$raw SetLineStyle [dict get $change lineStyle]];cmcp::check [$raw SetLineWidth [dict get $change lineWidth]]
  cmcp::check [$obj SetLocation $location];cmcp::check [$obj SetRotation [dict get $change rotation]];cmcp::check [$obj SetMirror [dict get $change mirror]]
  cmcp::check [DboGraphicObject_sSetColor $owner [dict get $change lineColor]];cmcp::check [$obj SetColor [dict get $change lineColor]]
 }
 cmcp::check [$page MarkModified];cmcp::check [$sch MarkModified $page];cmcp::check [$sch SavePage $page]
 cmcp::check [$d SaveSchematic $sch];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8;if {$rc} {puts $f [cmcp::obj saved false error [cmcp::q $message]]} else {puts $f [cmcp::obj saved true operation [cmcp::q "${operation}_graphic_line"]]}} finally {close $f}
if {$rc} {exit 1}
