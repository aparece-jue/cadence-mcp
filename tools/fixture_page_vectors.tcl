lassign $argv install target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {x y} {DboTclHelper_sMakeCPoint $x $y}
set session "";set phase open;set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];ck $st;set sch [$d GetSchematic [cs HALFADD] $st];ck $st;set page [$sch GetPage [cs MCP_PLACE] $st];ck $st
 set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 700 1 0 0 0 7 0 1 16]
 foreach rotation {0 1 2 3} {
  set i 0
  foreach kind {line box ellipse arc polygon polyline bezier text} {
   set phase "${rotation}_$kind";set loc [pt [expr {200+150*$i}] [expr {1000+200*$rotation}]];set rect [DboTclHelper_sMakeCRect -10 -20 50 40]
   switch -- $kind {
    line {set obj [$page NewGraphicLineInst $st [pt -10 5] [pt 50 35] $loc $rotation]}
    box {set obj [$page NewGraphicBoxInst $st $rect $loc $rotation]}
    ellipse {set obj [$page NewGraphicEllipseInst $st $rect $loc $rotation]}
    arc {set obj [$page NewGraphicArcInst $st $rect [pt 50 10] [pt 20 -20] $loc $rotation]}
    polygon {set obj [$page NewGraphicPolygonInst $st $loc $rotation]}
    polyline {set obj [$page NewGraphicPolylineInst $st $loc $rotation]}
    bezier {set obj [$page NewGraphicBezierInst $st $loc $rotation]}
    text {set text "[format %c 0x4e2d][format %c 0x6587] \[x\]\$;\nR1 / R10";set obj [$page NewGraphicCommentTextInst $st $rect $loc [cs $text] $font $rotation]}
   }
   ck $st;if {$obj eq "NULL"} {error missing_instance}
   if {$kind in {polygon polyline bezier}} {
    if {$kind eq "polygon"} {set raw [$obj GetDboPolygon]} elseif {$kind eq "polyline"} {set raw [$obj GetDboPolyline]} else {set raw [$obj GetDboBezier]}
    foreach p {{-10 5} {10 -15} {30 35} {50 5}} {ck [$raw NewPoint [pt {*}$p]]}
   }
   if {$kind ne "text"} {
    if {$kind eq "line"} {set raw [$obj GetDboLine]}
    if {$kind eq "box"} {set raw [$obj GetDboBox]}
    if {$kind eq "ellipse"} {set raw [$obj GetDboEllipse]}
    if {$kind eq "arc"} {set raw [$obj GetDboArc]}
    ck [$raw SetLineStyle 2];ck [$raw SetLineWidth 1]
    if {$kind in {box ellipse polygon}} {ck [$raw SetFillStyle 1];ck [$raw SetHatchStyle 0]}
   }
   ck [$obj SetLocation $loc];ck [$obj SetMirror [expr {$rotation%2}]];incr i
  }
 }
 set phase save;ck [$page MarkModified];ck [$sch MarkModified $page];ck [$sch SavePage $page];ck [$d SaveSchematic $sch];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
