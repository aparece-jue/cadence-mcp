# Add original per-instance user/display overrides to an owned copy only.
lassign $argv install target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];ck $st
 set s [$d GetSchematic [cs HALFADD] $st];ck $st;set page [$s GetPage [cs MCP_PLACE] $st];ck $st
 set it [$page NewPartInstsIter $st];ck $st;set count 0
 try {
  for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
   ck $st;set name [cs ""];ck [$part GetReference $name];set ref [DboTclHelper_sGetConstCharPtr $name]
   if {$ref ni {R101 R102}} {continue}
   set value [join [list \u7f13\u5b58 {[x]$;} [format %c 34] [format %c 92] [format %c 10] TAG] ""]
   set prop [$part NewUserProp [cs MCP_TAG] [cs $value] $st];ck $st
   if {$prop eq "NULL"} {error missing_property}
   set display [$part GetDisplayProp [cs Value] $st];ck $st
   if {$display eq "NULL"} {error missing_display}
   ck [$display SetLocation [DboTclHelper_sMakeCPoint 17 23]];ck [$display SetRotation 2]
   incr count
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {$count!=2} {error missing_targets}
 ck [$page MarkModified];ck [$s MarkModified $page];ck [$s SavePage $page];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];puts -nonewline $f [cmcp::obj failed [expr {$rc?"true":"false"}] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
