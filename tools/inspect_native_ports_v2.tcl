# Trusted read-only owned-fixture reader; retain native net identity, no geometric inference.
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cs {v} {return [DboTclHelper_sMakeCString $v]}
proc str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc pt {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
set session "";set phase load;set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set phase open
 set phase open_design;set d [$session GetDesignAndSchematics [cs $design] $st];ck $st
 if {$d eq "NULL"} {error missing_design}
 set ports {};set wires {};set count 0;set si 0;set phase views;set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];ck $st
 try {
  for {set v [$vi NextView $st]} {$v ne "NULL"} {set v [$vi NextView $st]} {
   ck $st;set s [DboViewToDboSchematic $v];set sn [cs "schematic-[incr si]"];set pi [$s NewPagesIter $st];ck $st;set pageOrdinal 0
   try {
    for {set p [$pi NextPage $st]} {$p ne "NULL"} {set p [$pi NextPage $st]} {
     ck $st;set pn [cs "page-[incr pageOrdinal]"];set netIds {};set ni 0;set wi 0;set it [$p NewWiresIter $st];ck $st
     try {
      for {set w [$it NextWire $st]} {$w ne "NULL"} {set w [$it NextWire $st]} {
       ck $st;if {[incr count]>100000} {error object_limit};set ns [DboState];set net [$w GetNet $ns];ck $ns
       if {$net eq "NULL"} {error missing_wire_net}
       if {![dict exists $netIds $net]} {dict set netIds $net "net-[incr ni]"}
       set points {};set np [$w GetPointCount $st];ck $st
       if {$np<2 || $np>10000} {error point_limit}
       for {set j 0} {$j<$np} {incr j} {if {[incr count]>100000} {error object_limit};lappend points [pt [$w GetPoint $j $st]];ck $st}
       lappend wires [cmcp::obj schematicId [cmcp::q [str $sn]] pageOrdinal [cmcp::q [str $pn]] netGroup [cmcp::q [dict get $netIds $net]] points [cmcp::arr $points]]
      };ck $st
     } finally {delete_DboPageWiresIter $it}
     set phase ports;set it [$p NewPortsIter $st $::IterDefs_ALL];ck $st
     try {
      for {set o [$it NextPort $st]} {$o ne "NULL"} {set o [$it NextPort $st]} {
       ck $st;if {[incr count]>100000} {error object_limit};set phase port_name;set nameState [DboState];set name [DboNetSymbolInstance_sGetNetName $o $nameState];ck $nameState;set phase port_source;set symbol [cs ""];ck [$o GetSourceSymbolName $symbol]
       set phase port_geometry;set location [pt [$o GetLocation $st]];ck $st;set hot [pt [$o GetOffsetHotSpot $st]];ck $st;set type [$o GetPinType $st];ck $st
       set ns [DboState];set net [$o GetNet $ns];set group null;set netName null
       if {$net eq "NULL"} {if {[$ns Failed] && [$ns Code]!=1021} {ck $ns}} else {
        ck $ns;if {![dict exists $netIds $net]} {dict set netIds $net "net-[incr ni]"}
        set group [cmcp::q [dict get $netIds $net]];set nn [cs ""];ck [$net GetNetName $nn];set netName [cmcp::q [str $nn]]
       }
       lappend ports [cmcp::obj schematicId [cmcp::q [str $sn]] pageOrdinal [cmcp::q [str $pn]] name [cmcp::q [str $name]] sourceSymbol [cmcp::q [str $symbol]] pinType $type location $location hotSpot $hot netGroup $group netName $netName]
      };ck $st
     } finally {delete_DboPagePortsIter $it}
    };ck $st
   } finally {delete_DboSchematicPagesIter $pi}
  };ck $st
 } finally {delete_DboLibViewsIter $vi}
 set result [cmcp::obj passed true ports [cmcp::arr $ports] wires [cmcp::arr $wires]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj passed false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
