# Read a bound global/offpage metadata snapshot, with no save or caller program.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
source [file join [file dirname [info script]] dbo_net_symbol_metadata.tcl]
if {$argc!=10} {exit 2}
lassign $argv install design output schematicName pageName kind nativeId name x y
if {$kind ni {global offpage} || ![string is integer -strict $nativeId]} {exit 2}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 lassign [cmcp::qualifiedPage $d $schematicName $pageName] schematic page
 set st [DboState]
 if {$kind eq "global"} {set it [$page NewGlobalsIter $st];set next NextGlobal;set remove delete_DboPageGlobalsIter} else {set it [$page NewOffPageConnectorsIter $st $::IterDefs_ALL];set next NextOffPageConnector;set remove delete_DboPageOffPageConnectorsIter};cmcp::check $st
 set matches {};set count 0
 try {for {set obj [$it $next $st]} {$obj ne "NULL"} {set obj [$it $next $st]} {
  cmcp::check $st;if {[incr count]>10000} {error symbol_limit};set id [$obj GetId $st];cmcp::check $st;set n [cmcp::cs ""];cmcp::check [$obj GetName $n];set h [$obj GetOffsetHotSpot $st];cmcp::check $st
  if {($nativeId==0 || $nativeId==$id) && [cmcp::str $n] eq $name && [DboTclHelper_sGetCPointX $h]==$x && [DboTclHelper_sGetCPointY $h]==$y} {lappend matches [list $obj $id]}
 }} finally {$remove $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_symbol_end}
 if {[llength $matches]!=1} {error ambiguous_symbol_metadata};lassign [lindex $matches 0] obj id
 set result [cmcp::obj nativeId $id metadata [cmcp::netSymbolMetadata $obj]];set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f $result} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "SYMBOL_METADATA_READ_ERROR: $message";exit 1}
