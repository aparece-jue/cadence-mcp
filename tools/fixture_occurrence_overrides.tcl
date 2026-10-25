# Owned fixture only: two occurrence overrides of one shared primitive definition.
lassign $argv install target output helper
source $helper
proc cs {s} {DboTclHelper_sMakeCString $s}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc child {occ reference} {
 set st [DboState];set it [$occ NewChildrenIter $st $::IterDefs_INSTS];ck $st;set matches {}
 try {
  for {set node [$it NextOccurrence $st]} {$node ne "NULL"} {set node [$it NextOccurrence $st]} {
   ck $st;set node [DboOccurrenceToDboInstOccurrence $node];set name [cs ""];ck [$node GetReferenceDesignator $name]
   if {[DboTclHelper_sGetConstCharPtr $name] eq $reference} {lappend matches $node}
  }
 } finally {delete_DboOccurrenceChildrenIter $it}
 if {[llength $matches]!=1} {error ambiguous_fixture_path};return [lindex $matches 0]
}
set session "";set phase open
set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cs $target] $st];ck $st;set root [$d GetRootOccurrence $st];ck $st
 set a [child [child $root halfadd_A] U3A];set b [child [child $root halfadd_B] U3C]
 set phase definition;set partA [$a GetPartInst $st];ck $st;set partB [$b GetPartInst $st];ck $st
 if {$partA ne $partB} {error fixture_not_shared_definition}
 set prop [$partA NewUserProp [cs MCP_DEF_TAG] [cs DEF_SHARED] $st];ck $st;if {$prop eq "NULL"} {error missing_definition_property}
 set phase occurrence
 set tail "[format %c 0x4e2d][format %c 0x6587]\[x\]\$;\nEND"
 foreach {label occ} [list A $a B $b] {
  set prop [$occ NewUserProp [cs MCP_SCOPE_TAG] [cs "$label$tail"] $st];ck $st;if {$prop eq "NULL"} {error missing_occurrence_property}
  ck [$occ MarkModified]
 }
 set prop [$a NewUserProp [cs Value] [cs OCC_A_VALUE] $st];ck $st;if {$prop eq "NULL"} {error missing_value_override}
 ck [$partA MarkModified];set phase save;set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];ck $st;set pages {};set schematics {}
 try {
  for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
   ck $st;set sch [DboViewToDboSchematic $view];lappend schematics $sch;set pi [$sch NewPagesIter $st];ck $st
   try {for {set page [$pi NextPage $st]} {$page ne "NULL"} {set page [$pi NextPage $st]} {ck $st;lappend pages [list $sch $page]}} finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 foreach pair $pages {lassign $pair sch page;ck [$page MarkModified];ck [$sch MarkModified $page];ck [$sch SavePage $page]}
 foreach sch $schematics {ck [$d SaveSchematic $sch]}
 ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
