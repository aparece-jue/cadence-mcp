# Fixed deliberate electrical conflict fixture on a copied two-filter design only.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=4} {exit 2};lassign $argv root design output operation
if {$operation ni {write read}} {exit 2}
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc rows {page} {
 set rows {};set selected {};set st [DboState];set it [$page NewPartInstsIter $st];ck $st
 try {
  while {1} {
   set st [DboState];set part [$it NextPartInst $st];if {$part eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error part_iterator};break};ck $st
   set ref [cs ""]; $part GetReference $ref;set ref [DboTclHelper_sGetConstCharPtr $ref];set st [DboState];set pit [$part NewPinsIter $st $::IterDefs_ALL 1];ck $st
   try {
    while {1} {
     set st [DboState];set pin [$pit NextPin $st];if {$pin eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error pin_iterator};break};ck $st
     set number [cs ""];ck [$pin GetPinNumber $number];set number [DboTclHelper_sGetConstCharPtr $number];set st [DboState];set type [$pin GetPinType $st];ck $st
     lappend rows [cmcp::obj reference [cmcp::q $ref] number [cmcp::q $number] type $type]
     if {($ref eq "R1" && $number eq "2") || ($ref eq "C1" && $number eq "1")} {lappend selected $pin}
    }
   } finally {delete_DboPartInstPinsIter $pit}
  }
 } finally {delete_DboPagePartInstsIter $it}
 return [list $rows $selected]
}
set session "";set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $design] $st];ck $st
 set st [DboState];set s [$d GetSchematic [cs LPFilters] $st];ck $st;set st [DboState];set it [$s NewPagesIter $st];ck $st
 set st [DboState];set page [$it NextPage $st];ck $st;delete_DboSchematicPagesIter $it
 lassign [rows $page] before targets
 if {$operation eq "write"} {
  if {[llength $targets]!=2} {error target_count}
  if {![info exists ::DboValue_DBO_OUT] || $::DboValue_DBO_OUT!=2} {error output_enum_mismatch}
  foreach pin $targets {ck [$pin SetPinType $::DboValue_DBO_OUT]}
  ck [$page MarkModified];ck [$s MarkModified $page];ck [$s SavePage $page];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
 }
 lassign [rows $page] after ignored
 set result [cmcp::obj saved [expr {$operation eq "write"?"true":"false"}] before [cmcp::arr $before] after [cmcp::arr $after]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8;if {$rc} {puts $f [cmcp::obj error [cmcp::q $message]]} else {puts $f $result}} finally {close $f}
if {$rc} {exit 1}
