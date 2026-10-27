source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root library output
proc cs {v} {return [DboTclHelper_sMakeCString $v]}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session GetLibAndSchematics [cs $library] $state];ck $state
set sym [$lib GetPortSymbol [cs PORTLEFT-L] $state];ck $state
if {$sym eq "NULL" || [$sym GetObjectType]!=34} {error wrong_symbol_type}
set rect [$sym GetBoundingBox];set top [DboTclHelper_sGetCRectTopLeft $rect];set bottom [DboTclHelper_sGetCRectBottomRight $rect]
set pins {};set it [$sym NewPinsIter $state];ck $state;set endCode 0
try {
 for {set i 0} {$i<32} {incr i} {
  set step [DboState];set pin [$it NextPin $step]
  if {$pin eq "NULL"} {set endCode [$step Code];if {[$step Failed] && $endCode!=1022} {ck $step};break}
  ck $step;lappend pins [pt [$pin GetHotSpot $state]];ck $state
 }
} finally {delete_DboSymbolPinsIter $it}
delete_DboSession $session
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj symbol [cmcp::q PORTLEFT-L] topLeft [pt $top] bottomRight [pt $bottom] pins [cmcp::arr $pins] iteratorEndCode $endCode]} finally {close $f}
