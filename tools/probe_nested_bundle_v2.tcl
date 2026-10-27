# Fixed private fixture: no client Tcl, no real-design writes.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root target output mode
if {$mode ni {create read}} {exit 2}
proc cs {value} {return [DboTclHelper_sMakeCString $value]}
proc text {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc ck {state} {if {[$state Failed]} {error "dbo_status_[$state Code]"}}
proc readMembers {map bundleName} {
 set bundle [$map GetBundle [cs $bundleName]]
 if {$bundle eq "NULL"} {error missing_bundle}
 set it [$map NewBundleNetIter [cs $bundleName] $::DboBundleType_NETSITER_UNEXPANDED]
 if {$it eq "NULL" || ![llength [info commands delete_DboBundleNetIter]]} {error missing_bundle_net_iterator}
 set rows {};set complete 0
 try {
  for {set i 0} {$i<32} {incr i} {
   set name [cs ""];set next [$it Next $name];set value [text $name]
   if {$value eq "" && $next==0} {set complete 1;break}
   if {$value eq "" || $next ni {0 1}} {error invalid_bundle_next}
   set member [$bundle GetMember [cs $value] FALSE]
   if {$member eq "NULL"} {error missing_direct_member}
   set ownName [cs ""];ck [$member GetName $ownName]
   lappend rows [cmcp::obj iteratorName [cmcp::q $value] name [cmcp::q [text $ownName]] type [$member GetBundleType] width [$member GetWidth] position [$bundle GetPosition [cs $value]] iteratorCode $next]
  }
 } finally {delete_DboBundleNetIter $it}
 if {!$complete} {error incomplete_bundle_members}
 return [cmcp::obj name [cmcp::q $bundleName] members [cmcp::arr $rows]]
}
set session "";set phase load;set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState];set phase open
 set d [$session GetDesignAndSchematics [cs $target] $state];ck $state
 if {$d eq "NULL"} {error no_design}
 set phase template_map;set map [$d GetBundleTemplateMap]
 if {$map eq "NULL"} {error no_template_map}
 if {$mode eq "create"} {
  foreach name {B_CHILD B_TOP} {
   set phase "create_$name";set created [DboTclHelper_sMakeBool FALSE]
   set bundle [$map AddBundleTemplate [cs $name] $d 0 $created]
   if {$bundle eq "NULL" || ![DboTclHelper_sGetBool $created]} {error template_not_created}
   DboTclHelper_sDeleteBool $created
  }
  set child [$map GetBundle [cs B_CHILD]];set top [$map GetBundle [cs B_TOP]]
  set phase child_scalar;ck [$child AddMember [cs READY] $::DboBundleType_SCALAR]
  set phase child_bus;ck [$child AddMember [cs {DATA[7..0]}] $::DboBundleType_BUS 8]
  set phase parent_scalar;ck [$top AddMember [cs CTRL] $::DboBundleType_SCALAR]
  set phase nested_member;ck [$map AddBundleMember [cs B_CHILD] [cs B_TOP] $::DboBundleType_BUNDLE $d]
  set phase mark_modified;$map MarkModifiedDesign
  set phase save;ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
 }
 set phase read_members;set rows {}
 foreach name {B_CHILD B_TOP} {lappend rows [readMembers $map $name]}
 set result [cmcp::obj passed true mode [cmcp::q $mode] bundles [cmcp::arr $rows]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj passed false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
