package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_package_properties.tcl]
if {$argc!=4} {exit 2}
lassign $argv root target request output
if {[file size $request]>16777216} {exit 2}
set f [open $request];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 16777217]]} finally {close $f}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase opening
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $target] $state];cmcp::check $state
 set pkg [$lib GetPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
 set actual [cmcp::packagePropertyDict $pkg];set before [dict get $spec beforeProperties]
 set phase checking_before
 foreach key {packageName referenceTemplate footprint pcbLibrary designator userPropsPermitted} {
  if {[dict get $actual $key] ne [dict get $before $key]} {error old_package_fields_mismatch}
 }
 set oldProps {};foreach p [dict get $before userProperties] {dict set oldProps [dict get $p name] $p}
 if {[dict size $oldProps]!=[llength [dict get $actual userProperties]]} {error old_package_properties_count}
 foreach p [dict get $actual userProperties] {
  set name [dict get $p name]
  if {![dict exists $oldProps $name]} {error missing_old_user_property}
  foreach key {value nativeType editable deletable} {if {[dict get $p $key] ne [dict get $oldProps $name $key]} {error old_user_property_mismatch}}
 }
 set phase setting_fields
 dict for {key value} [dict get $spec changes] {
  switch -- $key {
   referenceTemplate {cmcp::check [$pkg SetReferenceTemplate [cmcp::cs $value]]}
   footprint {cmcp::check [$pkg SetPCBFootprint [cmcp::cs $value]]}
   pcbLibrary {cmcp::check [$pkg SetPCBLib [cmcp::cs $value]]}
   default {error unsupported_package_field}
  }
 }
 foreach change [dict get $spec userChanges] {
  set phase editing_user_property;set name [dict get $change name];set operation [dict get $change operation]
  set props [$pkg NewUserPropsIter $state];cmcp::check $state;set selected ""
  try {
   for {set prop [$props NextUserProp $state]} {$prop ne "NULL"} {set prop [$props NextUserProp $state]} {
    cmcp::check $state;set pn [cmcp::cs ""];cmcp::check [$prop GetName $pn]
    if {[cmcp::str $pn] eq $name} {if {$selected ne ""} {error duplicate_user_property};set selected $prop}
   }
  } finally {delete_DboUserPropsIter $props}
  if {[$state Failed] && [$state Code]!=1022} {error unexpected_user_property_end}
  if {$operation eq "delete"} {
   if {$selected eq "" || ![$selected IsDeletable]} {error undeletable_user_property}
   cmcp::check [$pkg DeleteUserProp [cmcp::cs $name]]
  } elseif {$operation eq "set"} {
   if {$selected eq ""} {
    set state [DboState];set selected [$pkg NewUserProp [cmcp::cs $name] [cmcp::cs [dict get $change value]] $state];cmcp::check $state
    if {$selected eq "NULL"} {error missing_new_user_property}
   } else {
    set state [DboState];set type [$selected GetType $state];cmcp::check $state
    if {$type!=0 || ![$selected IsEditable]} {error typed_or_locked_user_property}
    cmcp::check [$selected SetStringValue [cmcp::cs [dict get $change value]]]
   }
  } else {error invalid_user_operation}
 }
 # NewUserProp alone may not dirty the containing package. Mark both levels
 # explicitly; the package overload on DboLib is void, not a DboState.
 set phase marking_modified;cmcp::check [$pkg MarkModified]
 $lib MarkModified $pkg
 cmcp::check [$lib MarkModified]
 set phase save;cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
 set result [cmcp::obj saved true packageId [cmcp::q [dict get $spec packageId]]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: package edit failed at ${phase}: $message";exit 1}
