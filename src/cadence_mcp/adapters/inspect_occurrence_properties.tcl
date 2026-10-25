# Fixed occurrence path selection and separate native effective/user/definition layers.
source [file join [file dirname [info script]] json.tcl]
package require json
proc cmcp::cs {s} {DboTclHelper_sMakeCString $s}
proc cmcp::str {s} {DboTclHelper_sGetConstCharPtr $s}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::effective {object} {
 set st [DboState];set it [$object NewEffectivePropsIter $st];cmcp::check $st;set rows {}
 try {
  set name [cmcp::cs ""];set value [cmcp::cs ""];set type [DboTclHelper_sMakeDboValueType];set editable [DboTclHelper_sMakeInt]
  while {1} {
   set next [$it NextEffectiveProp $name $value $type $editable]
   if {[$next OK]!=1} {if {[$next Code]!=1022} {error "unexpected_effective_end_[$next Code]"};break}
   if {[llength $rows]>=512 || [string length [cmcp::str $value]]>16384} {error property_limit}
   lappend rows [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
  }
 } finally {delete_DboEffectivePropsIter $it}
 return [cmcp::arr $rows]
}
proc cmcp::user {object} {
 set st [DboState];set it [$object NewUserPropsIter $st];cmcp::check $st;set rows {}
 try {
  for {set prop [$it NextUserProp $st]} {$prop ne "NULL"} {set prop [$it NextUserProp $st]} {
   cmcp::check $st;if {[llength $rows]>=512} {error property_limit}
   set name [cmcp::cs ""];set value [cmcp::cs ""];cmcp::check [$prop GetName $name];cmcp::check [$prop GetStringValue $value]
   if {[string length [cmcp::str $value]]>16384} {error property_value_limit}
   lappend rows [cmcp::obj name [cmcp::q [cmcp::str $name]] value [cmcp::q [cmcp::str $value]]]
  }
 } finally {delete_DboUserPropsIter $it}
 if {[$st Failed] && [$st Code]!=1022} {error unexpected_user_iterator_end}
 return [cmcp::arr $rows]
}
lassign $argv install design request output
set session "";set phase request
set rc [catch {
 if {[file size $request]>32768} {error request_limit}
 set f [open $request];try {fconfigure $f -encoding utf-8;set spec [json::json2dict [read $f 32769]]} finally {close $f}
 set segments [dict get $spec segments];if {[llength $segments]>64} {error depth_limit};if {![llength $segments]} {error root_properties_unverified}
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 set phase root;set occurrence [$d GetRootOccurrence $st];cmcp::check $st;if {$occurrence eq "NULL"} {error missing_root}
 set ancestors {};set count 0
 foreach segment $segments {
  if {$occurrence in $ancestors} {error recursive_hierarchy};lappend ancestors $occurrence
  set recursive [$occurrence IsRecursive $st];cmcp::check $st;if {$recursive} {error recursive_hierarchy}
  set it [$occurrence NewChildrenIter $st $::IterDefs_INSTS];cmcp::check $st;set matches {}
  try {
   for {set child [$it NextOccurrence $st]} {$child ne "NULL"} {set child [$it NextOccurrence $st]} {
    cmcp::check $st;if {[incr count]>10000} {error object_limit}
    set child [DboOccurrenceToDboInstOccurrence $child];set ref [cmcp::cs ""];cmcp::check [$child GetReferenceDesignator $ref]
    if {[cmcp::str $ref] eq $segment} {lappend matches $child}
   }
  } finally {delete_DboOccurrenceChildrenIter $it}
  if {[$st Failed] && [$st Code]!=1022} {error unexpected_child_iterator_end}
  if {[llength $matches]!=1} {error ambiguous_occurrence_path};set occurrence [lindex $matches 0]
 }
 set phase verify_identity;set raw [cmcp::cs ""];cmcp::check [$occurrence GetPathName $raw];set hier [cmcp::cs ""];cmcp::check [$occurrence GetHierPathName $hier]
 if {[cmcp::str $raw] ne [dict get $spec path] || [cmcp::str $hier] ne [dict get $spec hierarchicalPath]} {error occurrence_identity_changed}
 set phase layers;set effective [cmcp::effective $occurrence];set user [cmcp::user $occurrence];set definition null
 if {[llength $segments]} {
  set part [$occurrence GetPartInst $st];cmcp::check $st;if {$part eq "NULL"} {error missing_definition}
  set id [$part GetId $st];cmcp::check $st;set ref [cmcp::cs ""];cmcp::check [$part GetReference $ref]
  set full [cmcp::cs ""];set device [cmcp::cs ""]
  if {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE} {
   set kind placed;set placed [DboPartInstToDboPlacedInst $part];cmcp::check [$placed GetReferenceDesignator $full];cmcp::check [$placed GetDeviceDesignator $device]
  } elseif {[$part GetObjectType]==$::DboBaseObject_DRAWN_INSTANCE} {set kind drawn;cmcp::check [$part GetReferenceDesignator $full]} else {error unsupported_definition_type}
  set definition [cmcp::obj nativeId $id reference [cmcp::q [cmcp::str $ref]] fullReference [cmcp::q [cmcp::str $full]] deviceDesignator [cmcp::q [cmcp::str $device]] kind [cmcp::q $kind] effective [cmcp::effective $part] user [cmcp::user $part]]
 }
 set result [cmcp::obj effective $effective user $user definition $definition]
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: occurrence properties $phase: $message";exit 1}
