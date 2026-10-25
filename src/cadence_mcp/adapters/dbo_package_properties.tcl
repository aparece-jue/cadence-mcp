namespace eval cmcp {variable packageChars 0}
proc cmcp::packagePropertyDict {package} {
 variable packageChars
 set name [cmcp::cs ""];cmcp::check [$package GetName $name]
 set template [cmcp::cs ""];cmcp::check [$package GetReferenceTemplate $template]
 set footprint [cmcp::cs ""];cmcp::check [$package GetPCBFootprint $footprint]
 set pcbLibrary [cmcp::cs ""];cmcp::check [$package GetPCBLib $pcbLibrary]
 set designator [cmcp::cs ""];cmcp::check [$package GetDesignator $designator]
 set state [DboState];set permitted [$package GetUserPropsPermitted $state];cmcp::check $state
 set expectedCount [$package GetUserPropsCount $state];cmcp::check $state
 set it [$package NewUserPropsIter $state];cmcp::check $state;set props {}
 try {
  for {set prop [$it NextUserProp $state]} {$prop ne "NULL"} {set prop [$it NextUserProp $state]} {
   cmcp::check $state;if {[llength $props]>=1024} {error user_property_limit}
   set pn [cmcp::cs ""];set pv [cmcp::cs ""];cmcp::check [$prop GetName $pn];cmcp::check [$prop GetStringValue $pv]
   set type [$prop GetType $state];cmcp::check $state
   if {[string length [cmcp::str $pn]]>256 || [string length [cmcp::str $pv]]>16384} {error property_text_limit}
   incr packageChars [expr {[string length [cmcp::str $pn]]+[string length [cmcp::str $pv]]}]
   if {$packageChars>4194304} {error property_budget}
   lappend props [dict create name [cmcp::str $pn] value [cmcp::str $pv] nativeType $type editable [$prop IsEditable] deletable [$prop IsDeletable]]
  }
 } finally {delete_DboUserPropsIter $it}
 if {[$state Failed] && [$state Code]!=1022} {error unexpected_user_property_iterator_end}
 if {[llength $props]!=$expectedCount} {error incomplete_user_property_count}
 return [dict create packageName [cmcp::str $name] referenceTemplate [cmcp::str $template] footprint [cmcp::str $footprint] pcbLibrary [cmcp::str $pcbLibrary] designator [cmcp::str $designator] userPropsPermitted $permitted userProperties $props]
}
proc cmcp::packagePropertiesJson {row} {
 set props {}
 foreach p [dict get $row userProperties] {
  lappend props [cmcp::obj name [cmcp::q [dict get $p name]] value [cmcp::q [dict get $p value]] nativeType [dict get $p nativeType] editable [dict get $p editable] deletable [dict get $p deletable]]
 }
 return [cmcp::obj packageName [cmcp::q [dict get $row packageName]] referenceTemplate [cmcp::q [dict get $row referenceTemplate]] footprint [cmcp::q [dict get $row footprint]] pcbLibrary [cmcp::q [dict get $row pcbLibrary]] designator [cmcp::q [dict get $row designator]] userPropsPermitted [dict get $row userPropsPermitted] userProperties [cmcp::arr $props]]
}
