# Original owned object-count/pose fixture, using a private capsym copy.
lassign $argv install library target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase create
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session CreateDesign $st [cs $target] [cs TOP]];ck $st;set sch [$d GetRootSchematic $st];ck $st
 set lib [$session GetLibAndSchematics [cs $library] $st];ck $st
 set global [$lib GetGlobalSymbol [cs VCC] $st];ck $st;set offpage [$lib GetOffPageSymbol [cs OFFPAGELEFT-L] $st];ck $st
 set copy [$d CopySymbol $global [cs READ_GLOBAL] $st];ck $st;set copy [$d CopySymbol $offpage [cs READ_OFF] $st];ck $st
 set global [$d GetGlobalSymbol [cs READ_GLOBAL] $st];ck $st;set offpage [$d GetOffPageSymbol [cs READ_OFF] $st];ck $st
 foreach name {PAGE_A PAGE_B EMPTY} {
  set phase "page_$name";set page [$sch NewPage $st [cs $name]];ck $st
  if {$name ne "EMPTY"} {
   foreach mirror {0 1} {
    foreach rotation {0 1 2 3} {
     set x [expr {200+150*$rotation}];set y [expr {200+200*$mirror}]
     set object [$page NewGlobal $st [cs DUP_SUPPLY] $global [DboTclHelper_sMakeCPoint $x $y] $rotation $mirror];ck $st
     set object [$page NewOffPageConnector $st [cs DUP_LINK] $offpage [DboTclHelper_sMakeCPoint $x [expr {$y+70}]] $rotation $mirror];ck $st
    }
   }

  }
  ck [$page MarkModified];ck [$sch MarkModified $page];ck [$sch SavePage $page]
 }
 set phase save;ck [$d SaveSchematic $sch];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
