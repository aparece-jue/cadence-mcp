# Fixed global/offpage edit diagnostic; only isolated copied designs.
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_net_symbol_metadata.tcl]
if {$argc!=4} {exit 2}
lassign $argv root design specPath output
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
if {[file size $specPath]>65536} {exit 2}
set f [open $specPath];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]];close $f
set kind [dict get $spec kind];if {$kind ni {global offpage}} {exit 2}
set session "";set phase load
set log [open [file join [file dirname $output] phases.log] {WRONLY CREAT EXCL}]
proc cmcp::tracePhase {args} {global phase log;puts $log $phase;flush $log}
trace add variable phase write cmcp::tracePhase
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set phase open_design;set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
 if {$d eq "NULL"} {error missing_input}
 set matches {};set phase locate_page
 set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
 try {
  for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
   cmcp::check $state;set s [DboViewToDboSchematic $v];set n [cmcp::cs ""];cmcp::check [$s GetName $n]
   if {[cmcp::str $n] ne [dict get $spec schematicName]} {continue}
   set pi [$s NewPagesIter $state];cmcp::check $state
   try {
    for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
     cmcp::check $state;set n [cmcp::cs ""];cmcp::check [$p GetName $n]
     if {[cmcp::str $n] eq [dict get $spec pageName]} {lappend matches [list $s $p]}
    }
   } finally {delete_DboSchematicPagesIter $pi}
  }
 } finally {delete_DboLibViewsIter $vi}
 if {[llength $matches]!=1} {error ambiguous_page};lassign [lindex $matches 0] schematic page
 set state [DboState];set phase locate_symbol
 if {$kind eq "global"} {set it [$page NewGlobalsIter $state];set next NextGlobal;set remove delete_DboPageGlobalsIter} else {set it [$page NewOffPageConnectorsIter $state $::IterDefs_ALL];set next NextOffPageConnector;set remove delete_DboPageOffPageConnectorsIter};cmcp::check $state
 set found {};set count 0
 try {
  for {set obj [$it $next $state]} {$obj ne "NULL"} {set obj [$it $next $state]} {
   cmcp::check $state;if {[incr count]>10000} {error symbol_limit}
   set id [$obj GetId $state];cmcp::check $state
   if {$id==[dict get $spec nativeId]} {lappend found $obj}
  }
 } finally {$remove $it}
 if {[llength $found]!=1} {error ambiguous_symbol};set obj [lindex $found 0]
 set n [cmcp::cs ""];cmcp::check [$obj GetName $n]
 set pt [$obj GetLocation $state];cmcp::check $state
 set r [$obj GetRotation $state];cmcp::check $state
 set m [$obj GetMirror $state];cmcp::check $state
 set h [$obj GetOffsetHotSpot $state];cmcp::check $state
 if {[cmcp::str $n] ne [dict get $spec oldName] || [list [DboTclHelper_sGetCPointX $pt] [DboTclHelper_sGetCPointY $pt]] ne [dict get $spec oldLocation] || $r!=[dict get $spec oldRotation] || $m!=[dict get $spec oldMirror] || [list [DboTclHelper_sGetCPointX $h] [DboTclHelper_sGetCPointY $h]] ne [dict get $spec oldHotSpot]} {error stale_symbol}
 set phase mutate_symbol
 switch -- [dict get $spec operation] {
  set_pose {
   set phase pose_locate_wire
   set pose [dict get $spec pose];set ws [DboState];set wires [$page NewWiresIter $ws];cmcp::check $ws;set foundWires {}
   try {for {set wire [$wires NextWire $ws]} {$wire ne "NULL"} {set wire [$wires NextWire $ws]} {
    cmcp::check $ws;if {[$wire GetId $ws]==[dict get $spec wireNativeId]} {lappend foundWires $wire};cmcp::check $ws
   }} finally {delete_DboPageWiresIter $wires}
   if {[$ws Failed] && [$ws Code]!=1022} {error unexpected_wire_iterator_end}
   if {[llength $foundWires]!=1} {error ambiguous_terminal_wire};set wire [lindex $foundWires 0];set ws [DboState]
   if {[$wire GetPointCount $ws]!=2} {error terminal_wire_point_count};cmcp::check $ws
   set phase pose_validate_wire;set actual {}
   foreach index {0 1} {set q [$wire GetPoint $index $ws];cmcp::check $ws;lappend actual [list [DboTclHelper_sGetCPointX $q] [DboTclHelper_sGetCPointY $q]]}
   if {$actual ne [dict get $pose oldWirePoints]} {error old_terminal_wire_mismatch}
   set phase pose_old_binding;set sn [$obj GetNet $ws];cmcp::check $ws;set wn [$wire GetNet $ws];cmcp::check $ws
   if {$sn eq "NULL" || $sn ne $wn} {error old_terminal_binding_mismatch}
   # Offpage orientation setters report failure; reconstruction has an explicit cache policy.
   if {[dict get $pose recreate]} {
    set phase pose_recreate_offpage
    if {$kind ne "offpage" || ![dict get $pose sourceCacheRebind]} {error unexpected_recreation_policy}
    set metadata [::json::json2dict [cmcp::netSymbolMetadata $obj]]
    set sourceName [cmcp::cs ""];cmcp::check [$obj GetSourceSymbolName $sourceName]
    set definition [$d GetOffPageSymbol $sourceName $ws];cmcp::check $ws;if {$definition eq "NULL"} {error missing_cached_symbol}
    set color [$obj GetColor $ws];cmcp::check $ws
    set replacement [$page NewOffPageConnector $ws [cmcp::cs [dict get $spec oldName]] $definition [DboTclHelper_sMakeCPoint {*}[dict get $pose location]] [dict get $pose rotation] [dict get $pose mirror]];cmcp::check $ws
    if {$replacement eq "NULL"} {error offpage_recreation_failed}
    set newColor [$replacement GetColor $ws];cmcp::check $ws;if {$newColor!=$color} {cmcp::check [$replacement SetColor $color]}
    cmcp::copyNetSymbolMetadata $obj $replacement
    set copied [::json::json2dict [cmcp::netSymbolMetadata $replacement]]
    foreach field {user display} {if {[dict get $metadata $field] ne [dict get $copied $field]} {error "recreated_${field}_mismatch"}}
    set expectedEffective {}
    foreach row [dict get $metadata effective] {
     set propName [dict get $row name];set value [dict get $row value]
     if {$propName eq "Location X-Coordinate"} {set value [lindex [dict get $pose location] 0]}
     if {$propName eq "Location Y-Coordinate"} {set value [lindex [dict get $pose location] 1]}
     if {$propName eq "Source Library"} {
      if {![string equal -nocase [file extension $value] .dsn]} {error unsupported_source_cache_rebind}
      set value __OWNED_OUTPUT_CACHE__
     }
     dict set expectedEffective $propName $value
    }
    set actualEffective {};foreach row [dict get $copied effective] {dict set actualEffective [dict get $row name] [dict get $row value]}
    if {[lsort [dict keys $expectedEffective]] ne [lsort [dict keys $actualEffective]]} {error recreated_effective_keys_mismatch}
    dict for {propName value} $expectedEffective {
     if {$propName eq "Source Library" && $value eq "__OWNED_OUTPUT_CACHE__"} {
      if {![string equal -nocase [file normalize [dict get $actualEffective $propName]] [file normalize $design]]} {error recreated_source_cache_binding_mismatch}
     } elseif {[dict get $actualEffective $propName] ne $value} {error "recreated_effective_value_mismatch:$propName"}
    }
    cmcp::check [$page DeleteOffPageConnector $obj];set obj $replacement
   } else {
    set phase pose_mirror
    if {[dict get $pose mirror]!=[dict get $spec oldMirror]} {cmcp::check [$obj SetMirror [dict get $pose mirror]]}
    set phase pose_rotation
    if {[dict get $pose rotation]!=[dict get $spec oldRotation]} {cmcp::check [$obj SetRotation [dict get $pose rotation]]}
    set phase pose_location
    cmcp::check [$obj SetLocation [DboTclHelper_sMakeCPoint {*}[dict get $pose location]]]
   }
   set phase pose_new_hotspot;set h [$obj GetOffsetHotSpot $ws];cmcp::check $ws
   if {[list [DboTclHelper_sGetCPointX $h] [DboTclHelper_sGetCPointY $h]] ne [dict get $pose expectedHotSpot]} {error expected_hotspot_mismatch}
   set phase pose_wire_endpoint;set scalar [DboWireToDboWireScalar $wire]
   cmcp::check [$scalar SetPoint [dict get $pose wireEndIndex] [DboTclHelper_sMakeCPoint {*}[dict get $pose expectedHotSpot]]]
  }
  set_name {cmcp::check [$obj SetName [cmcp::cs [dict get $spec name]]]}
  delete {if {$kind eq "global"} {cmcp::check [$page DeleteGlobal $obj]} else {cmcp::check [$page DeleteOffPageConnector $obj]}}
  default {error invalid_operation}
 }
 set phase save_page;cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
 set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
 set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;if {$rc} {puts $f [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} else {puts $f [cmcp::obj saved true operation [cmcp::q [dict get $spec operation]]]};close $f
if {$rc} {exit 1}
