# Fixed private fault injection into an owned saved DSN only.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
package require json
if {$argc!=4} {exit 2}
lassign $argv root design request output
set f [open $request];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] schematic page
 set state [DboState];set it [$page NewPartInstsIter $state];cmcp::check $state;set matches {}
 try {
  for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
   cmcp::check $state;set ref [cmcp::cs ""];cmcp::check [$part GetReference $ref]
   if {[cmcp::str $ref] eq [dict get $spec reference]} {lappend matches $part}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $matches]!=1} {error ambiguous_target}
 set state [DboState];set placed [DboPartInstToDboPlacedInst [lindex $matches 0]];set libpart [$placed GetPart $state];cmcp::check $state
 set it [$libpart NewVectorsIter $state $::IterDefs_ALL];cmcp::check $state;set targets {}
 try {
  for {set vector [$it NextVector $state]} {$vector ne "NULL"} {set vector [$it NextVector $state]} {
   cmcp::check $state;set type [$vector GetObjectType]
   if {([dict get $spec kind] eq "ellipse" && $type==$::DboBaseObject_ELLIPSE) || ([dict get $spec kind] eq "text" && $type==$::DboBaseObject_COMMENT_TEXT)} {lappend targets $vector}
  }
 } finally {delete_DboGraphicObjectVectorsIter $it}
 if {[llength $targets]!=1} {error ambiguous_vector}
 if {[dict get $spec kind] eq "ellipse"} {
  set v [DboVectorToDboEllipse [lindex $targets 0]];cmcp::check [$v SetBoundingBox [DboTclHelper_sMakeCRect -6 -4 6 4]]
 } else {
  set v [DboVectorToDboCommentText [lindex $targets 0]];set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 900 0 0 0 0 7 0 1 16];cmcp::check [$v SetFont $font]
 }
 cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page];cmcp::check [$d SaveSchematic $schematic];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
 set result [cmcp::obj saved true]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
