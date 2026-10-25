# Read all display-font descriptors in one owned interpreter; no GUI or save.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
lassign $argv install design output
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 set rows {};set count 0;set bytes 0
 set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st
 try {
  for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
   cmcp::check $st;set s [DboViewToDboSchematic $view];set pi [$s NewPagesIter $st];cmcp::check $st
   try {
    for {set page [$pi NextPage $st]} {$page ne "NULL"} {set page [$pi NextPage $st]} {
     cmcp::check $st;set it [$page NewPartInstsIter $st];cmcp::check $st
     try {
      for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
       cmcp::check $st;if {[incr count]>128} {error font_instance_limit}
       set id [$part GetId $st];cmcp::check $st;set fonts {};set di [$part NewDisplayPropsIter $st];cmcp::check $st
       try {
        for {set prop [$di NextProp $st]} {$prop ne "NULL"} {set prop [$di NextProp $st]} {
         cmcp::check $st;if {[llength $fonts]>=512} {error display_limit}
         set name [cmcp::cs ""];cmcp::check [$prop GetName $name]
         set font [DboDisplayProp_sGetFont $prop $st];cmcp::check $st;set descriptor [cmcp::vectorFont $font]
         set isDefault [$prop IsFontDefault $st];cmcp::check $st;set defaultType [$prop GetDefaultFontType $st];cmcp::check $st
         incr bytes [string length [cmcp::str $name]];if {$bytes>1048576} {error name_budget}
         lappend fonts [cmcp::obj name [cmcp::q [cmcp::str $name]] fontDefault $isDefault defaultFontType $defaultType font [cmcp::arr [list [cmcp::q [lindex $descriptor 0]] {*}[lrange $descriptor 1 end]]]]
        }
       } finally {delete_DboDisplayPropsIter $di}
       lappend rows [cmcp::obj nativeId $id fonts [cmcp::arr $fonts]]
      }
     } finally {delete_DboPagePartInstsIter $it}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "DISPLAY_FONT_READ_ERROR: $message";exit 1}
