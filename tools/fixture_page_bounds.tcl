# Private predeclared boundary fixture only; no real design or install write.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=4} {exit 2};lassign $argv root target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {p} {DboTclHelper_sMakeCPoint {*}$p}
proc mark {v} {global output;set f [open [file join [file dirname $output] phase.txt] w];puts $f $v;close $f}
set session "";set rc [catch {
 mark opening
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];ck $st
 set st [DboState];set sch [$d GetSchematic [cs HALFADD] $st];ck $st
 foreach {name width height pin metric} {BOUND_MAIN 9700 7200 100 0 BOUND_OTHER 12700 10160 254 1 BOUND_EMPTY 9700 7200 100 0 BOUND_ZERO 0 0 100 0} {
  mark "new_page_$name"
  set st [DboState];set page [$sch NewPage $st [cs $name]];ck $st
  if {$name ne "BOUND_ZERO"} {mark "size_$name";$page SetPageSizeInfo $width $height $pin $metric}
  if {$name eq "BOUND_MAIN"} {
   foreach points {{{10 10} {960 710}} {{0 0} {970 720}} {{-1 100} {10 100}} {{960 100} {971 100}} {{100 -1} {100 10}} {{100 710} {100 721}}} {
    mark "line_$points";lassign $points a b;lassign $a x y;lassign $b xx yy;set st [DboState];set obj [$page NewGraphicLineInst $st [pt {0 0}] [pt [list [expr {$xx-$x}] [expr {$yy-$y}]]] [pt $a] 0];ck $st
   }
   set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
   foreach {text x y w h} {EDGE_BOX 950 700 20 20 OVER_BOX 950 700 21 21 OUT_ANCHOR -1 0 20 20} {
    mark "text_$text";set rect [DboTclHelper_sMakeCRect $x $y [expr {$x+$w}] [expr {$y+$h}]];set st [DboState];set obj [$page NewGraphicCommentTextInst $st $rect [pt {0 0}] [cs $text] $font 0];ck $st;set raw [$obj GetDboCommentText];ck [$raw SetBoundingBox $rect];ck [$raw SetLocation [pt [list $x $y]]]
   }
  }
  if {$name eq "BOUND_OTHER"} {mark metric_line;set st [DboState];set obj [$page NewGraphicLineInst $st [pt {0 0}] [pt {500 400}] [pt {0 0}] 0];ck $st}
  mark "save_$name";ck [$page MarkModified];ck [$sch MarkModified $page];ck [$sch SavePage $page]
 }
 mark save_design;ck [$d SaveSchematic $sch];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;puts $f [cmcp::obj saved [expr {$rc?"false":"true"}] error [cmcp::q $message]]} finally {close $f}
if {$rc} {exit 1}
