# Read-only source geometry and instance coordinate frames. Never saves a file.
lassign $argv install library design output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {p} {cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]}
proc rect {r} {set a [DboTclHelper_sGetCRectTopLeft $r];set b [DboTclHelper_sGetCRectBottomRight $r];cmcp::arr [list [DboTclHelper_sGetCPointX $a] [DboTclHelper_sGetCPointY $a] [DboTclHelper_sGetCPointX $b] [DboTclHelper_sGetCPointY $b]]}
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set st [DboState]
set lib [$session GetLibAndSchematics [cs $library] $st];ck $st;set definitions {}
foreach {kind name method} {global VCC GetGlobalSymbol offpage OFFPAGELEFT-L GetOffPageSymbol} {
 set sym [$lib $method [cs $name] $st];ck $st;set pins {};set it [$sym NewPinsIter $st];ck $st
 try {
  for {set pin [$it NextPin $st]} {$pin ne "NULL"} {set pin [$it NextPin $st]} {ck $st;lappend pins [pt [$pin GetHotSpot $st]];ck $st}
 } finally {delete_DboSymbolPinsIter $it}
 lappend definitions [cmcp::obj kind [cmcp::q $kind] name [cmcp::q $name] bounds [rect [$sym GetBoundingBox]] pins [cmcp::arr $pins]]
}
set d [$session GetDesignAndSchematics [cs $design] $st];ck $st;set s [$d GetSchematic [cs TOP] $st];ck $st;set p [$s GetPage [cs PAGE_A] $st];ck $st;set instances {}
foreach {kind make next remove} {global NewGlobalsIter NextGlobal delete_DboPageGlobalsIter offpage NewOffPageConnectorsIter NextOffPageConnector delete_DboPageOffPageConnectorsIter} {
 set it [$p $make $st];ck $st
 try {
  for {set o [$it $next $st]} {$o ne "NULL"} {set o [$it $next $st]} {
   ck $st
   set location [pt [$o GetLocation $st]];ck $st;set hot [pt [$o GetHotSpot $st]];ck $st;set offset [pt [$o GetOffsetHotSpot $st]];ck $st
   set rotation [$o GetRotation $st];ck $st;set mirror [$o GetMirror $st];ck $st
   lappend instances [cmcp::obj kind [cmcp::q $kind] location $location hotSpot $hot offsetHotSpot $offset bounds [rect [$o GetBoundingBox]] rotation $rotation mirror $mirror]
  }
 } finally {$remove $it}
}
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj definitions [cmcp::arr $definitions] instances [cmcp::arr $instances]];close $f
