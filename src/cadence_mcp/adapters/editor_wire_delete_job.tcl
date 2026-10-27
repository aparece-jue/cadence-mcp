# Trusted fixed editor workflow. All arguments are literal typed plan data.
namespace eval ::cmcpEditorDelete {
 proc ck {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
 proc run {expectedPid active hostProject targetProject target schematic page occurrence x1 y1 x2 y2 net ax ay output marker nonce aliasesJson} {
  if {[pid]!=$expectedPid} {error wrong_process}
  if {![regexp {^[a-f0-9]{32}$} $nonce]} {error invalid_job_nonce}
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]] || [::cmcpBridge::dirty] ne "clean"} {error wrong_active_design}
  if {[dict size $::cmcpBridge::propertyPlans]} {error bridge_busy}
  if {[file exists $output] || [file exists $marker]} {error already_dispatched}
  foreach value [list $x1 $y1 $x2 $y2 $ax $ay] {if {![string is integer -strict $value] || abs($value)>1000000} {error invalid_coordinate}}
  set f [open $marker {WRONLY CREAT EXCL}];puts $f $nonce;close $f
  set phase open_output;set saved 0;set restored 0
  set caught [catch {
   Open $targetProject
   if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]]} {error wrong_output_design}
   set phase open_page
   set d [GetActivePMDesign];set st [DboState];set s [$d GetSchematic [DboTclHelper_sMakeCString $schematic] $st];ck $st
   set count [$s GetOccurrencesCount]
   if {![string is integer -strict $count] || $count<0 || $count>10000} {error occurrence_limit}
   if {$count>1 && $occurrence eq ""} {error explicit_editor_occurrence_required}
   if {$occurrence ne ""} {
    set names {}
    for {set i 0} {$i<$count} {incr i} {
     set occ [DboOccurrenceToDboInstOccurrence [$s GetOccurrencesAtPos $i]]
     if {$occ eq "NULL"} {error invalid_editor_occurrence}
     set ref [DboTclHelper_sMakeCString];ck [$occ GetReferenceDesignator $ref]
     lappend names [DboTclHelper_sGetConstCharPtr $ref]
    }
    if {[llength [lsearch -all -exact $names $occurrence]]!=1} {error invalid_editor_occurrence}
   }
   if {$occurrence eq ""} {OPage $schematic $page} else {OPage $schematic $page $occurrence}
   set st [DboState];set p [$s GetPage [DboTclHelper_sMakeCString $page] $st];ck $st
   if {[GetActivePage] ne $p || [GetActiveView] eq "NULL"} {error wrong_output_editor}
   set phase locate_wire
   set st [DboState];set it [$p NewWiresIter $st];ck $st;set matches {}
   try {
    for {set w [$it NextWire $st]} {$w ne "NULL"} {set w [$it NextWire $st]} {
     ck $st
     if {[$w GetPointCount $st]!=2} {ck $st;continue};ck $st
     set a [$w GetPoint 0 $st];ck $st;set b [$w GetPoint 1 $st];ck $st
     set first [list [DboTclHelper_sGetCPointX $a] [DboTclHelper_sGetCPointY $a]]
     set last [list [DboTclHelper_sGetCPointX $b] [DboTclHelper_sGetCPointY $b]]
     if {!(($first eq [list $x1 $y1] && $last eq [list $x2 $y2]) || ($last eq [list $x1 $y1] && $first eq [list $x2 $y2]))} {continue}
     set name [DboTclHelper_sMakeCString];ck [$w GetNetName $name]
     if {[DboTclHelper_sGetConstCharPtr $name] eq $net} {lappend matches $w}
    }
   } finally {delete_DboPageWiresIter $it}
   if {[llength $matches]!=1} {error ambiguous_wire}
   set w [lindex $matches 0];set declared [::json::json2dict $aliasesJson];set expected {}
   foreach row $declared {lappend expected [list [dict get $row name] {*}[dict get $row oldLocation]]}
   set actual {};set st [DboState];set it [$w NewAliasesIter $st];ck $st
   try {
    for {set alias [$it NextAlias $st]} {$alias ne "NULL"} {set alias [$it NextAlias $st]} {
     ck $st
     if {[llength $actual]>=32} {error alias_limit}
     set n [DboTclHelper_sMakeCString];ck [$alias GetName $n];set pt [$alias GetLocation $st];ck $st
     lappend actual [list [DboTclHelper_sGetConstCharPtr $n] [DboTclHelper_sGetCPointX $pt] [DboTclHelper_sGetCPointY $pt]]
    }
   } finally {delete_DboWireAliasesIter $it}
   if {[lsort $expected] ne [lsort $actual]} {error alias_identity_mismatch}
   set st [DboState];set ident [$w GetId $st];ck $st
   UnSelectAll
   SelectObjectById $ident
   set selected [GetSelectedObjects]
   if {[llength $selected]!=1} {error ambiguous_selection}
   set obj [lindex $selected 0];set st [DboState];set selectedId [$obj GetId $st];ck $st
   if {$selectedId!=$ident || [$obj GetObjectType]!=[$w GetObjectType]} {error wrong_selected_object}
   set phase delete_wire
   Delete
   set phase save
   set session $::DboSession_s_pDboSession;DboSession -this $session
   ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
   set saved 1
   if {[::cmcpBridge::dirty] ne "clean"} {error output_not_clean}
   set phase close_output
   SelectPMItem "Design Resources"
   CloseProject
   if {[file exists ${target}lck]} {error output_project_still_locked}
   set phase restore_host
   if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]]} {Open $hostProject}
   if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]] || [::cmcpBridge::dirty] ne "clean"} {error host_not_restored}
   # Native open/save/close invalidates prior logical sessions. A fresh session
   # may attach only after the original design is back, never during the switch.
   ::cmcpBridge::lifecycleStart
   set restored 1;set phase returned
  } message]
  if {$caught} {
   # Restore only a clean target. Never discard unsaved partial edits.
   catch {
    if {[string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]] && [::cmcpBridge::dirty] ne "clean"} {error unsaved_partial_output}
    if {[string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]] && [::cmcpBridge::dirty] eq "clean"} {
     SelectPMItem "Design Resources"
     CloseProject
    }
    if {[file exists ${target}lck]} {error output_project_still_locked}
    if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]]} {Open $hostProject}
    if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]] || [::cmcpBridge::dirty] ne "clean"} {error host_not_restored}
    ::cmcpBridge::lifecycleStart
    set restored 1
   }
  }
  set receipt [cmcp::obj jobId [cmcp::q $nonce] pid [pid] saved [expr {$saved?"true":"false"}] hostRestored [expr {$restored?"true":"false"}] invocationReturned [expr {$caught?"false":"true"}] phase [cmcp::q $phase] error [cmcp::q [expr {$caught?[string range $message 0 2047]:""}]]]
  set pending ${output}.pending;set f [open $pending {WRONLY CREAT EXCL}]
  try {fconfigure $f -encoding utf-8 -translation lf;puts $f $receipt} finally {close $f}
  file rename $pending $output
 }
}
