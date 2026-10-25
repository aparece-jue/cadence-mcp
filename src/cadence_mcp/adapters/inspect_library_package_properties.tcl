source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_package_properties.tcl]
if {$argc!=3} {exit 2}
lassign $argv root source output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set library [$session GetLibAndSchematics [cmcp::cs $source] $state];cmcp::check $state
 set it [$library NewPackagesIter $state];cmcp::check $state;set rows {}
 try {
  for {set package [$it NextPackage $state]} {$package ne "NULL"} {set package [$it NextPackage $state]} {
   cmcp::check $state;if {[llength $rows]>=10000} {error package_limit}
   lappend rows [cmcp::packagePropertiesJson [cmcp::packagePropertyDict $package]]
  }
 } finally {delete_DboLibPackagesIter $it}
 if {[$state Failed] && [$state Code]!=1022} {error unexpected_package_iterator_end}
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: package properties read failed: $message";exit 1}
