# Fixed metadata snapshots and native copies for global/offpage graphic instances.
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
proc cmcp::netSymbolMetadata {obj} {
 set users {};set displays {};set effective {};set total 0
 set st [DboState];set it [$obj NewUserPropsIter $st];cmcp::check $st
 try {for {set prop [$it NextUserProp $st]} {$prop ne "NULL"} {set prop [$it NextUserProp $st]} {
  cmcp::check $st;if {[llength $users]>=512} {error symbol_property_limit}
  set name [cmcp::cs ""];set value [cmcp::cs ""];cmcp::check [$prop GetName $name];cmcp::check [$prop GetStringValue $value]
  incr total [string bytelength [cmcp::str $name]];incr total [string bytelength [cmcp::str $value]];if {$total>1048576} {error symbol_property_budget}
  set type [$prop GetType $st];cmcp::check $st
  lappend users [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] nativeType $type editable [$prop IsEditable] deletable [$prop IsDeletable]]
 }} finally {delete_DboUserPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_user_end}
 set st [DboState];set it [$obj NewEffectivePropsIter $st];cmcp::check $st
 try {
  set name [cmcp::cs ""];set value [cmcp::cs ""];set type [DboTclHelper_sMakeDboValueType];set editable [DboTclHelper_sMakeInt]
  while {1} {
   set status [$it NextEffectiveProp $name $value $type $editable]
   if {![$status OK]} {if {[$status Code]!=1022} {cmcp::check $status};break}
   if {[llength $effective]>=512} {error symbol_property_limit}
   incr total [string bytelength [cmcp::str $name]];incr total [string bytelength [cmcp::str $value]];if {$total>1048576} {error symbol_property_budget}
   lappend effective [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
  }
 } finally {delete_DboEffectivePropsIter $it}
 set st [DboState];set it [$obj NewDisplayPropsIter $st];cmcp::check $st
 try {for {set prop [$it NextProp $st]} {$prop ne "NULL"} {set prop [$it NextProp $st]} {
  cmcp::check $st;if {[llength $displays]>=512} {error symbol_display_limit}
  set name [cmcp::cs ""];set value [cmcp::cs ""];cmcp::check [$prop GetName $name];cmcp::check [$prop GetValueString $value]
  set location [$prop GetLocation $st];cmcp::check $st;set rotation [$prop GetRotation $st];cmcp::check $st;set dtype [$prop GetDisplayType $st];cmcp::check $st;set color [$prop GetColor $st];cmcp::check $st
  set font [DboDisplayProp_sGetFont $prop $st];cmcp::check $st;set f [cmcp::vectorFont $font]
  set default [$prop IsFontDefault $st];cmcp::check $st;set defaultType [$prop GetDefaultFontType $st];cmcp::check $st
  lappend displays [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]] location [cmcp::arr [list [DboTclHelper_sGetCPointX $location] [DboTclHelper_sGetCPointY $location]]] rotation $rotation displayType $dtype color $color font [cmcp::arr [list [cmcp::q [lindex $f 0]] {*}[lrange $f 1 end]]] fontDefault $default defaultFontType $defaultType]
 }} finally {delete_DboDisplayPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_display_end}
 return [cmcp::obj user [cmcp::arr [lsort $users]] effective [cmcp::arr [lsort $effective]] display [cmcp::arr [lsort $displays]]]
}
proc cmcp::copyNetSymbolMetadata {old new} {
 set st [DboState];set it [$new NewDisplayPropsIter $st];cmcp::check $st;set defaults {}
 try {for {set prop [$it NextProp $st]} {$prop ne "NULL"} {set prop [$it NextProp $st]} {cmcp::check $st;if {[llength $defaults]>=512} {error symbol_display_limit};lappend defaults $prop}} finally {delete_DboDisplayPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_display_end}
 foreach prop $defaults {cmcp::check [$new DeleteDisplayProp $prop]}
 set st [DboState];set it [$old NewUserPropsIter $st];cmcp::check $st
 try {for {set prop [$it NextUserProp $st]} {$prop ne "NULL"} {set prop [$it NextUserProp $st]} {
  cmcp::check $st;set name [cmcp::cs ""];set value [cmcp::cs ""];cmcp::check [$prop GetName $name];cmcp::check [$prop GetStringValue $value]
  set created [$new NewUserProp $name $value $st];cmcp::check $st;if {$created eq "NULL"} {error user_property_copy_failed}
 }} finally {delete_DboUserPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_user_end}
 set st [DboState];set it [$old NewDisplayPropsIter $st];cmcp::check $st
 try {for {set prop [$it NextProp $st]} {$prop ne "NULL"} {set prop [$it NextProp $st]} {
  cmcp::check $st;set created [$new NewDisplayProp $st $prop];cmcp::check $st;if {$created eq "NULL"} {error display_property_copy_failed}
 }} finally {delete_DboDisplayPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_display_end}
}
