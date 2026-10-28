# Owned experiment using runtime-verified native constructors and official incremental annotation.
lassign $argv install target output helper mode
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase open
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];ck $st
 if {$mode eq "reset"} {
  set phase reset;set s [$d GetSchematic [cs HALFADD] $st];ck $st;set p [$s GetPage [cs MCP_PLACE] $st];ck $st
  set it [$p NewPartInstsIter $st];ck $st;set found {}
  try {
   for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
    ck $st;set ref [cs ""];ck [$part GetReference $ref]
    if {[DboTclHelper_sGetConstCharPtr $ref] eq "R101"} {lappend found $part}
   }
  } finally {delete_DboPagePartInstsIter $it}
  if {[llength $found]!=1} {error wrong_reset_target}
  ck [[lindex $found 0] SetReference [cs R?]]
 } elseif {$mode eq "annotate"} {
  set phase setup_annotation
  set manager [$d GetRefDesMgr];$manager RefreshInstanceRefDesMap
  set handler [DboRefDesQueryHandler];set options [RefDesQueryOptions]
  foreach setter {SetFillHolesBetweenDevices SetFillHolesForMultiPartPkg SetFillHolesForSinglePartPkg SetMatchNetsForCommonPins SetPreserveDesForHetero SetPreserveDesForHomo} {$options $setter 1}
  $options SetIncludeNonPrimitive 0
  $handler SetQueryOptions $options;$handler SetQueryMap [$manager GetInstanceRefDesMap]
  set rt [DboRefDesRTData];$rt setQueryOption $options
  set annotate [new_DboRefDesAnnotate $handler];DboRefDesAnnotate_SetDesign $annotate $d;DboRefDesAnnotate_SetRTData $annotate $rt
  set phase select_original_target
  set ts [DboState];set sch [$d GetSchematic [cs HALFADD] $ts];ck $ts;set page [$sch GetPage [cs MCP_PLACE] $ts];ck $ts
  set it [$page NewPartInstsIter $ts];ck $ts;set targets {}
  try {
   for {set part [$it NextPartInst $ts]} {$part ne "NULL"} {set part [$it NextPartInst $ts]} {
    ck $ts;set ref [cs ""];ck [$part GetReference $ref];set id [$part GetId $ts];ck $ts
    if {$id==2502 && [DboTclHelper_sGetConstCharPtr $ref] eq "R?"} {lappend targets $part}
   }
  } finally {delete_DboPagePartInstsIter $it}
  if {[llength $targets]!=1} {error explicit_original_target_missing}
  set phase native_explicit_list
  $handler AssignRefDesToList $targets
  set resultState [$rt GetDboState];ck $resultState
 } else {error invalid_mode}
 set phase save;set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];ck $st;set pages {};set schematics {}
 try {
  for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
   ck $st;set s [DboViewToDboSchematic $view];lappend schematics $s;set pi [$s NewPagesIter $st];ck $st
   try {for {set p [$pi NextPage $st]} {$p ne "NULL"} {set p [$pi NextPage $st]} {ck $st;lappend pages [list $s $p]}} finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 foreach pair $pages {lassign $pair s p;ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p]}
 foreach s $schematics {ck [$d SaveSchematic $s]}
 ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
