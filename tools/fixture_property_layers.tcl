# Original fixed query fixture; no wires and no existing design overwritten.
if {$argc!=5} {error "install target mode receipt helper"}
lassign $argv install target mode output helper
if {$mode ni {base override empty deleted} || [file exists $target]} {error invalid_target}
source $helper
proc cs {s} {DboTclHelper_sMakeCString $s}
proc check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set variant $mode
set mode duplicate
set session "";set phase create
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set d [$session CreateDesign $state [cs $target] [cs ROOT]];check $state
 set root [$d GetRootSchematic $state];check $state
 if {$mode eq "duplicate"} {
  set lib [$session GetLibAndSchematics [cs [file join $install tools capture library pspice analog.olb]] $state];check $state
  set source [$lib GetPackage [cs R] $state];check $state
  set pkg [$d CopyPackageAll $source [cs MCP_QUERY_R] $state];check $state
  set default [$pkg NewUserProp [cs MCP_PACKAGE_ONLY] [cs \u5e93\u9ed8\u8ba4\u503c] $state];check $state
  if {$default eq "NULL"} {error missing_default}
  set device [$pkg GetDevice [cs ""] $state];check $state
  set cell [$device GetCell $state];check $state
  set it [$cell NewPartsIter $state];check $state
  set parts {}
  try {for {set p [$it NextPart $state]} {$p ne "NULL"} {set p [$it NextPart $state]} {check $state;lappend parts $p}} finally {delete_DboCellPartsIter $it}
  if {[llength $parts]!=1} {error ambiguous_resistor}
  set part [lindex $parts 0]
  set default [$part NewUserProp [cs MCP_DEFAULT] [cs \u5e93\u9ed8\u8ba4\u503c] $state];check $state
  set aux [$d NewSchematic [cs AUX] $state];check $state
  set schematics [list $root $aux]
 } else {set schematics [list $root]}
 foreach s $schematics {
  set phase page
  set p [$s NewPage $state [cs SAME_PAGE]];check $state
  if {$mode eq "duplicate"} {
   foreach {ref x} {R1 300 R10 500} {
    set phase place_$ref
    set instance [$p NewPlacedInst $state [cs $ref] [cs MCP_QUERY_R] $part $device [DboTclHelper_sMakeCPoint $x 300]];check $state
    check [$instance SetReference [cs $ref]];check [$instance SetPartValue [cs 1k]]
    if {$s eq $root && $ref eq "R1"} {
     set unicode [join [list \u6599\u53f7 {[x]} {$} {;} [format %c 34] [format %c 92] [format %c 10] \u5c3e] ""]
     set prop [$instance NewUserProp [cs MCP_LOCAL] [cs $unicode] $state];check $state
     if {$variant ne "base"} {
      set value [expr {$variant eq "empty" ? "" : "\u663e\u5f0f\u8986\u76d6"}]
      set prop [$instance NewUserProp [cs MCP_DEFAULT] [cs $value] $state];check $state
      if {$variant eq "deleted"} {check [$instance DeleteUserProp [cs MCP_DEFAULT]]}
     }
     set display [$instance GetDisplayProp [cs Value] $state];check $state
     if {$display ne "NULL"} {check [$display SetLocation [DboTclHelper_sMakeCPoint 13 17]];check [$display SetRotation 0]}
    }
   }
  }
  check [$p MarkModified];check [$s MarkModified $p];check [$s SavePage $p]
  if {$mode eq "duplicate" && $s eq $root} {
   set p [$s NewPage $state [cs EMPTY_PAGE]];check $state
   check [$p MarkModified];check [$s MarkModified $p];check [$s SavePage $p]
  }
  check [$d SaveSchematic $s]
 }
 set phase save_design
 check [$session MarkAllLibForSave $d];check [$session SaveDesign $d]
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj caught $rc phase [cmcp::q $phase] message [cmcp::q [expr {$rc ? $message : ""}]] errorInfo [cmcp::q [expr {$rc ? [dict get $options -errorinfo] : ""}]]]} finally {close $f}
if {$rc} {exit 1}
