# Fixed read-only page size/units reader. Native iteration errors never imply a complete lookup.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=5} {exit 2};lassign $argv root design output schematicName pageName
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::size {p} {cmcp::arr [list [DboTclHelper_sGetCSizeX $p] [DboTclHelper_sGetCSizeY $p]]}
proc cmcp::point {p} {cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]}
set session "";set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState]
 set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 if {$d eq "NULL"} {error missing_design}
 set st [DboState];set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st;set matches {};set n 0
 try {
  while {1} {
   set st [DboState];set v [$vi NextView $st]
   if {$v eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error view_iterator_error};break};cmcp::check $st
   if {[incr n]>100000} {error object_limit}
   set sch [DboViewToDboSchematic $v];set name [cmcp::cs ""];cmcp::check [$sch GetName $name]
   if {[cmcp::str $name] ne $schematicName} {continue}
   set st [DboState];set pi [$sch NewPagesIter $st];cmcp::check $st
   try {
    while {1} {
     set st [DboState];set p [$pi NextPage $st]
     if {$p eq "NULL"} {if {[$st Failed] && [$st Code]!=1022} {error page_iterator_error};break};cmcp::check $st
     if {[incr n]>100000} {error object_limit}
     set name [cmcp::cs ""];cmcp::check [$p GetName $name]
     if {[cmcp::str $name] eq $pageName} {lappend matches $p}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error ambiguous_page};set p [lindex $matches 0]
 set st [DboState];set size [$p GetSize $st];cmcp::check $st
 set name [cmcp::cs ""];cmcp::check [$p GetSizeName $name]
 set fields [list sizeName [cmcp::q [cmcp::str $name]] pageWidth [$p GetPageWidth] pageHeight [$p GetPageHeight] pinToPin [$p GetPinToPin] isMetric [$p GetIsMetric] size [cmcp::size $size] docUnits [cmcp::size [$p GetDocUnits 0]] drawableDocUnits [cmcp::size [$p GetDocUnits 1]] docUnitsPerInch [$p GetDocUnitsPerInch] physicalGranularity [$p GetPhysicalGranularity] pinToPinScaleFactor [$p GetPinToPinScaleFactor]]
 foreach {key method} {borderDisplayed GetBorderDisplayed borderPrinted GetBorderPrinted gridRefDisplayed GetGridRefDisplayed gridRefPrinted GetGridRefPrinted titleBlockDisplayed GetTitleBlockDisplayed titleBlockPrinted GetTitleBlockPrinted ansiGridRefs GetANSIGridRefs} {
  set st [DboState];set value [$p $method $st];cmcp::check $st;lappend fields $key $value
 }
 foreach {key method} {outerBorderMargin GetOuterBorderMargin innerBorderMargin GetInnerBorderMargin} {
  set st [DboState];set value [$p $method $st];cmcp::check $st;lappend fields $key [cmcp::point $value]
 }
 set result [cmcp::obj {*}$fields]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: page dimensions failed: $message";exit 1}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f $result} finally {close $f}
