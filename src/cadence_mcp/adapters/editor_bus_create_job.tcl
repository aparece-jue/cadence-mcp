# Trusted fixed editor workflow. All arguments are literal typed plan data.
namespace eval ::cmcpEditorBus {
 proc context {target page} {
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]] || [GetActivePage] ne $page} {error output_context_changed}
 }
 proc ck {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
 proc run {expectedPid active hostProject targetProject target schematic page occurrence x1 y1 x2 y2 net ax ay output marker nonce specJson} {
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
   set spec [::json::json2dict $specJson]
   set prefix [dict get $spec prefix]
   if {![regexp {^[A-Za-z_][A-Za-z0-9_]{0,63}$} $prefix]} {error invalid_bus_prefix}
   set seen [dict create];set st [DboState];set it [$p NewBusEntriesIter $st];ck $st
   try {
    for {set e [$it NextBusEntry $st]} {$e ne "NULL"} {set e [$it NextBusEntry $st]} {
     ck $st;set id [$e GetId $st];ck $st;dict set seen $id 1
     if {[dict size $seen]>100000} {error entry_limit}
    }
   } finally {delete_DboPageBusEntriesIter $it}
   set phase bus
   context $target $p
   PlaceBus [expr {$x1/100.0}] [expr {$y1/100.0}] [expr {$x2/100.0}] [expr {$y2/100.0}]
   EndPlace
   context $target $p
   PlaceNetAlias [expr {$x1/100.0}] [expr {$y1/100.0}] $net
   EndPlace
   foreach branch [dict get $spec branches] {
    set bit [dict get $branch index]
    lassign [dict get $branch entryPoint] ex ey
    lassign [dict get $branch endPoint] sx sy
    lassign [dict get $branch wireEnd] wx wy
    set phase entry_$bit
    context $target $p
    PlaceBusEntry [expr {$ex/100.0}] [expr {$ey/100.0}] FALSE
    EndPlace
    set st [DboState];set it [$p NewBusEntriesIter $st];ck $st;set fresh {}
    try {
     for {set e [$it NextBusEntry $st]} {$e ne "NULL"} {set e [$it NextBusEntry $st]} {
      ck $st;set id [$e GetId $st];ck $st
      if {![dict exists $seen $id]} {lappend fresh [list $id $e]}
     }
    } finally {delete_DboPageBusEntriesIter $it}
    if {[llength $fresh]!=1} {error ambiguous_native_entry}
    lassign [lindex $fresh 0] id e;dict set seen $id 1
    ck [$e SetEntryPoint [DboTclHelper_sMakeCPoint $ex $ey]]
    ck [$e SetEndPoint [DboTclHelper_sMakeCPoint $sx $sy]]
    set phase scalar_$bit
    context $target $p
    PlaceWire [expr {$sx/100.0}] [expr {$sy/100.0}] [expr {$wx/100.0}] [expr {$wy/100.0}]
    EndPlace
    context $target $p
    PlaceNetAlias [expr {$wx/100.0}] [expr {$wy/100.0}] ${prefix}${bit}
    EndPlace
   }
   context $target $p
   set phase save
   set session $::DboSession_s_pDboSession;DboSession -this $session
   ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p];ck [$d SaveSchematic $s];ck [$session MarkAllLibForSave $d];ck [$session SaveDesign $d]
   set saved 1
   if {[::cmcpBridge::dirty] ne "clean"} {error output_not_clean}
   set phase close_output
   if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]]} {error output_context_changed}
   SelectPMItem "Design Resources"
   if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $target]]} {error output_context_changed}
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
