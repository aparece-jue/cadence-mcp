# Internal owned fixture only; does not certify full bus connectivity.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root target receipt mode
if {$mode ni {descending ascending missing_member detached_entry}} {exit 2}
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
proc cmcp::pt {x y} {return [DboTclHelper_sMakeCPoint $x $y]}
set session "";set phase open
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $target] $state];cmcp::check $state
    if {$d eq "NULL"} {error no_design}
    set s [$d GetRootSchematic $state];cmcp::check $state
    set pi [$s NewPagesIter $state];cmcp::check $state
    set p [$pi NextPage $state];cmcp::check $state
    delete_DboSchematicPagesIter $pi
    if {$p eq "NULL"} {error no_page}
    set state [DboState]
    set phase bus
    set name [expr {$mode eq "ascending" ? {DATA[0..7]} : {DATA[7..0]}}]
    set bus [$p NewWireBus $state [cmcp::cs $name] [cmcp::pt 600 200] [cmcp::pt 600 700]];cmcp::check $state
    if {$bus eq "NULL"} {error no_bus}
    set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
    set alias [$bus NewAlias $state [cmcp::cs $name] [cmcp::pt 600 200] $font 0 0];cmcp::check $state
    set n [expr {$mode eq "missing_member" ? 7 : 8}]
    for {set i 0} {$i<$n} {incr i} {
        set y [expr {220+50*$i}]
        set x [expr {$mode eq "detached_entry" && $i==7 ? 590 : 600}]
        set phase "entry_$i"
        set entry [$p NewBusEntry $state [cmcp::pt $x $y] [cmcp::pt 620 [expr {$y+20}]]];cmcp::check $state
        if {$entry eq "NULL"} {error no_entry}
        set phase "scalar_$i"
        set wire [$p NewWireScalar $state [cmcp::pt 620 [expr {$y+20}]] [cmcp::pt 800 [expr {$y+20}]]];cmcp::check $state
        if {$wire eq "NULL"} {error no_scalar}
        set alias [$wire NewAlias $state [cmcp::cs "DATA$i"] [cmcp::pt 800 [expr {$y+20}]] $font 0 0];cmcp::check $state
        if {$alias eq "NULL"} {error no_alias}
    }
    set phase save
    cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]
    cmcp::check [$d SaveSchematic $s];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q bus_fixture] mode [cmcp::q $mode]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $receipt {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
