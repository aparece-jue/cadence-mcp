# Trusted fixed editor workflow. All arguments are literal typed plan data.
namespace eval ::cmcpEditorJunction {
 proc ck {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
 proc run {expectedPid active hostProject targetProject target schematic page occurrence x y wireA wireB output marker nonce} {
  if {[pid]!=$expectedPid} {error wrong_process}
  if {![regexp {^[a-f0-9]{32}$} $nonce]} {error invalid_job_nonce}
  if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize $active]] || [::cmcpBridge::dirty] ne "clean"} {error wrong_active_design}
  if {[dict size $::cmcpBridge::propertyPlans]} {error bridge_busy}
  if {[file exists $output] || [file exists $marker]} {error already_dispatched}
  foreach value [list $x $y] {if {![string is integer -strict $value] || abs($value)>1000000} {error invalid_coordinate}}
  if {![string is integer -strict $wireA] || ![string is integer -strict $wireB] || $wireA==$wireB} {error invalid_wire_ids}
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
   set phase locate_crossing
   set st [DboState];set it [$p NewWiresIter $st];ck $st;set found {}
   try {
    for {set w [$it NextWire $st]} {$w ne "NULL"} {set w [$it NextWire $st]} {
     ck $st;set id [$w GetId $st];ck $st
     if {$id==$wireA || $id==$wireB} {
      if {[DboWireToDboWireScalar $w] eq "NULL"} {error not_scalar_wire}
      lappend found $id
     }
    }
   } finally {delete_DboPageWiresIter $it}
   if {[lsort -integer $found] ne [lsort -integer [list $wireA $wireB]]} {error wrong_crossing_wire_ids}
   set phase place_junction
   PlaceJunction [expr {$x/100.0}] [expr {$y/100.0}]
   EndPlace
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
