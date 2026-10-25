# Owned fixture: relocate an unbound B unit across existing pages and add reference displays.
lassign $argv install target output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc stcheck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase open
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];stcheck $st
 set s [$d GetSchematic [cs HALFADD] $st];stcheck $st
 set p [$s GetPage [cs MCP_PLACE] $st];stcheck $st
 set dest [$s GetPage [cs HALFADD] $st];stcheck $st
 if {$p eq "NULL" || $dest eq "NULL"} {error missing_page}
 set phase find_unit;set selected {};set it [$p NewPartInstsIter $st];stcheck $st
 try {
  for {set instance [$it NextPartInst $st]} {$instance ne "NULL"} {set instance [$it NextPartInst $st]} {
   stcheck $st;set ref [cs ""];stcheck [$instance GetReference $ref]
   if {[DboTclHelper_sGetConstCharPtr $ref] ne "U501"} {continue}
   set placed [DboPartInstToDboPlacedInst $instance];set suffix [cs ""];stcheck [$placed GetDeviceDesignator $suffix]
   dict set selected [DboTclHelper_sGetConstCharPtr $suffix] $placed
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[dict size $selected]!=2 || ![dict exists $selected A] || ![dict exists $selected B]} {error wrong_group}
 set phase crosspage_copy;set original [dict get $selected B]
 set copy [$dest NewPlacedInst $original $st];stcheck $st
 if {$copy eq "NULL"} {error missing_copy}
 stcheck [$p DeletePartInst $original]
 dict set selected B $copy
 set phase display_properties
 set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
 dict for {suffix instance} $selected {
  set value "[format %c 0x4f4d][format %c 0x53f7] U501 / U501$suffix / U5010 \[x\]\$;"
  set prop [$instance NewUserProp [cs MCP_NOTE] [cs $value] $st];stcheck $st;if {$prop eq "NULL"} {error missing_user_property}
  foreach {name x y rot type} {{Part Reference} 17 23 2 1 Reference 19 31 1 2 MCP_NOTE 29 37 3 1} {
   set display [$instance NewDisplayProp $st [cs $name] [DboTclHelper_sMakeCPoint $x $y] $rot $font 3];stcheck $st
   if {$display eq "NULL"} {error missing_display}
   stcheck [$display SetDisplayType $type]
  }
 }
 set phase save
 foreach page [list $p $dest] {stcheck [$page MarkModified];stcheck [$s MarkModified $page];stcheck [$s SavePage $page]}
 stcheck [$d SaveSchematic $s];stcheck [$session MarkAllLibForSave $d];stcheck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
