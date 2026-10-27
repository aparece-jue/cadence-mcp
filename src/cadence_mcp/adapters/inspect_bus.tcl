# Independent wire bus members and entry binding inventory; no network inference.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
proc cmcp::wire_ref {entry method index} {
    set state [DboState];set wire [$entry $method $state]
    if {$wire eq "NULL"} {
        if {[$state Failed] && [$state Code]!=1021} {cmcp::check $state}
        return null
    }
    cmcp::check $state
    if {![dict exists $index $wire]} {error missing_linked_wire}
    return [cmcp::q [dict get $index $wire]]
}
namespace eval cmcp {variable textBytes 0}
proc cmcp::boundedName {value} {
    variable textBytes
    if {[string length $value]>4096} {error name_limit}
    incr textBytes [string bytelength $value]
    if {$textBytes>4194304} {error text_limit}
    return $value
}
set session "";set phase open
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set phase open_design;set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error no_design}
    set wires {};set entries {};set phase views;set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state;set si 0;set total 0
    try {
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            set phase view_next;cmcp::check $state;set s [DboViewToDboSchematic $v];set sid "schematic-[incr si]"
            set ps [DboState];set phase pages;set pi [$s NewPagesIter $ps];cmcp::check $ps;set pn 0
            try {
                for {set p [$pi NextPage $ps]} {$p ne "NULL"} {set p [$pi NextPage $ps]} {
                    set phase page_next;cmcp::check $ps;set pid "$sid/page-[incr pn]";set index {};set wi 0;set es 0
                    set ws [DboState];set phase wires;set it [$p NewWiresIter $ws];cmcp::check $ws
                    try {
                        for {set w [$it NextWire $ws]} {$w ne "NULL"} {set w [$it NextWire $ws]} {
                            set phase wire_next;cmcp::check $ws
                            if {[incr total]>100000} {error object_limit}
                            set id "$pid/wire-[incr wi]";dict set index $w $id
                            set name [cmcp::cs ""];set phase wire_geometry
                            set stateWire [DboState];set np [$w GetPointCount $stateWire];cmcp::check $stateWire
                            if {$np<2 || $np>10000} {error point_limit}
                            set points {};for {set j 0} {$j<$np} {incr j} {if {[incr total]>100000} {error object_limit};set pt [$w GetPoint $j $stateWire];cmcp::check $stateWire;lappend points [cmcp::point $pt]}
                            set isBus [expr {[$w GetObjectType]==$::DboBaseObject_WIRE_BUS}]
                            set bundle false;set width 0;set members {}
                            if {$isBus} {
                                set phase bus_net
                                set busWire [DboWireToDboWireBus $w];set bundle [expr {[$busWire IsBundleObject] ? "true" : "false"}]
                                set net [$w GetNet $stateWire];cmcp::check $stateWire
                                if {$net eq "NULL"} {error missing_bus_net}
                                set bus [DboNetToDboNetBus $net]
                                set phase bus_name;cmcp::check [$bus GetNetName $name]
                                set width [$bus GetWidth $stateWire];cmcp::check $stateWire
                                if {$width<0 || $width>10000} {error member_limit}
                                for {set j 0} {$j<$width} {incr j} {
                                    if {[incr total]>100000} {error object_limit}
                                    set member [$bus GetMember $j $stateWire];cmcp::check $stateWire
                                    if {$member eq "NULL"} {error missing_bus_member}
                                    set mn [cmcp::cs ""];cmcp::check [$member GetNetName $mn]
                                    lappend members [cmcp::obj position $j name [cmcp::q [cmcp::boundedName [cmcp::str $mn]]]]
                                }
                            }
                            if {!$isBus} {set phase scalar_name;cmcp::check [$w GetNetName $name]}
                            lappend wires [cmcp::obj wireId [cmcp::q $id] pageId [cmcp::q $pid] isBus [expr {$isBus ? "true" : "false"}] isBundle $bundle name [cmcp::q [cmcp::boundedName [cmcp::str $name]]] points [cmcp::arr $points] width $width members [cmcp::arr $members]]
                        }
                    } finally {delete_DboPageWiresIter $it}
                    set phase entries
                    set st [DboState];set it [$p NewBusEntriesIter $st];cmcp::check $st
                    try {
                        for {set e [$it NextBusEntry $st]} {$e ne "NULL"} {set e [$it NextBusEntry $st]} {
                            cmcp::check $st
                            if {[incr total]>100000} {error object_limit}
                            set a [$e GetEntryPoint $st];cmcp::check $st;set b [$e GetEndPoint $st];cmcp::check $st
                            lappend entries [cmcp::obj entryId [cmcp::q "$pid/entry-[incr es]"] pageId [cmcp::q $pid] entryPoint [cmcp::point $a] endPoint [cmcp::point $b] entryWireId [cmcp::wire_ref $e GetEntryWire $index] endWireId [cmcp::wire_ref $e GetEndWire $index]]
                        }
                    } finally {delete_DboPageBusEntriesIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj wires [cmcp::arr $wires] entries [cmcp::arr $entries]]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    set f [open "$output.error.json" {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj phase [cmcp::q $phase] message [cmcp::q $message]]} finally {close $f}
    puts stderr "CADENCE_DBO_ERROR: bus inventory failed";exit 1
}
