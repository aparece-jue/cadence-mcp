# Fixed native existing-line probe on a separately owned copy, never a public eval.
if {$argc!=9} {exit 2}
lassign $argv install design output helper qualified nativeId rotation mirror operation
source $helper
source $qualified
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
if {![string is integer -strict $nativeId] || $rotation ni {0 1 2 3} || $mirror ni {0 1} || $operation ni {update delete}} {exit 2}
set session "";set phase open;set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 lassign [cmcp::qualifiedPage $d HALFADD MCP_PLACE] sch page
 set it [$page NewCommentGraphicsIter $st];cmcp::check $st;set found {};set count 0
 try {
  while {1} {
   set st [DboState];set obj [$it NextCommentGraphic $st]
   if {$obj eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error bad_iterator_end};break}
   cmcp::check $st;if {[incr count]>4096} {error graphic_limit}
   set id [$obj GetId $st];cmcp::check $st
   if {$id==$nativeId} {lappend found $obj}
  }
 } finally {delete_DboPageCommentGraphicsIter $it}
 if {[llength $found]!=1} {error ambiguous_line}
 set obj [lindex $found 0]
 if {[$obj GetObjectType]!=$::DboBaseObject_GRAPHIC_LINE_INST} {error wrong_graphic_type}
 set obj [DboGraphicInstanceToDboGraphicLineInst $obj]
 set phase $operation
 if {$operation eq "delete"} {
  cmcp::check [$page DeleteCommentGraphic $obj]
 } else {
  set raw [$obj GetDboLine];if {$raw eq "NULL"} {error missing_line_definition}
  cmcp::check [$raw SetStart [DboTclHelper_sMakeCPoint -20 15]]
  cmcp::check [$raw SetEnd [DboTclHelper_sMakeCPoint 40 55]]
  cmcp::check [$raw SetLineStyle 3];cmcp::check [$raw SetLineWidth 2]
  cmcp::check [$obj SetLocation [DboTclHelper_sMakeCPoint 700 800]]
  cmcp::check [$obj SetRotation $rotation];cmcp::check [$obj SetMirror $mirror]
  set owner [$raw GetOwner];if {$owner eq "NULL"} {error missing_line_owner}
  cmcp::check [DboGraphicObject_sSetColor $owner 8];cmcp::check [$obj SetColor 8]
 }
 set phase save
 cmcp::check [$page MarkModified];cmcp::check [$sch MarkModified $page];cmcp::check [$sch SavePage $page]
 cmcp::check [$d SaveSchematic $sch];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8;puts $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] error [cmcp::q [expr {$rc?$message:""}]]]} finally {close $f}
if {$rc} {exit 1}
