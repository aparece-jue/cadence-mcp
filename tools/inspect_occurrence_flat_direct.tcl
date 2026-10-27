# Internal read-only native probe. argv: install copiedDSN outputJSON
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
namespace eval cmcp {variable rows {};variable count 0;variable pins 0;variable flatIds {};variable phase init}
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
proc cmcp::walk {occ parent segments depth ancestors} {
    variable rows;variable count;variable pins;variable flatIds;variable phase
    if {$depth>64 || $count>=10000 || $occ in $ancestors || $occ eq "NULL"} {error "hierarchy_limit_or_cycle"}
    set state [DboState]
    if {[$occ IsRecursive $state]} {error "recursive_hierarchy"};cmcp::check $state
    set id "occ-[incr count]"
    set reference [cmcp::cs ""]
    if {$parent ne ""} {
        set phase reference
        cmcp::check [$occ GetReferenceDesignator $reference]
        lappend segments [cmcp::str $reference]
        set phase occurrence_device
        set part [$occ GetPartInst $state];cmcp::check $state
        if {$part eq "NULL"} {error "missing_part_instance"}
        set device "NULL"
        if {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE} {
            set placed [DboPartInstToDboPlacedInst $part]
            set package [$placed GetPackage $state];cmcp::check $state
            if {$package eq "NULL"} {error "missing_package"}
            set designator [cmcp::cs ""];cmcp::check [$occ GetDesignator $designator]
            set device [$package GetDevice $designator $state];cmcp::check $state
            if {$device eq "NULL"} {error "missing_occurrence_device"}
        }
        set phase port_iterator
        set it [$occ NewChildrenIter $state $::IterDefs_PORTS];cmcp::check $state
        try {
            for {set raw [$it NextOccurrence $state]} {$raw ne "NULL"} {set raw [$it NextOccurrence $state]} {
                cmcp::check $state
                if {[incr pins]>100000} {error "pin_limit"}
                set phase "port_instance:[cmcp::str $reference]"
                set port [DboOccurrenceToDboPortOccurrence $raw]
                set pin [$port GetPortInst $state];cmcp::check $state
                if {$pin eq "NULL"} {error "missing_port_instance"}
                set phase "pin_number:[cmcp::str $reference]";set number [cmcp::cs ""];set numberState [$pin GetPinNumber $number];set numberCode [$numberState Code];if {[$numberState Failed] && $numberCode!=1021} {cmcp::check $numberState}
                set phase "pin_name:[cmcp::str $reference]";set name [cmcp::cs ""];cmcp::check [$pin GetPinName $name]
                set occurrenceNumberPath [cmcp::cs ""];set pnState [$port GetPathNameNumber $occurrenceNumberPath];set occurrenceNumberCode [$pnState Code];if {[$pnState Failed] && $occurrenceNumberCode!=1021} {cmcp::check $pnState}
                set occurrencePhysicalNumber "null"
                if {$device ne "NULL"} {
                    set phase occurrence_physical_pin
                    set position [$pin GetPinPosition $state];cmcp::check $state
                    set mapped [cmcp::cs ""];cmcp::check [$device GetPinNumber $position $mapped]
                    set occurrencePhysicalNumber [cmcp::q [cmcp::str $mapped]]
                }
                set phase direct_port_occurrence_flat_net
                set flat [$port GetFlatNet]
                set flatId "null";set flatName "";set global "null";set netPath ""
                if {$flat ne "NULL"} {
                    if {![dict exists $flatIds $flat]} {dict set flatIds $flat "flat-[expr {[dict size $flatIds]+1}]"}
                    set flatId [cmcp::q [dict get $flatIds $flat]]
                    set fn [cmcp::cs ""];cmcp::check [$flat GetName $fn];set flatName [cmcp::str $fn]
                    set global [$flat GetIsGlobal $state];cmcp::check $state
                }
                set parts {};foreach s $segments {lappend parts [cmcp::q $s]}
                lappend rows [cmcp::obj occurrenceId [cmcp::q $id] instancePathSegments [cmcp::arr $parts] reference [cmcp::q [cmcp::str $reference]] number [cmcp::q [cmcp::str $number]] numberStatusCode $numberCode occurrencePhysicalNumber $occurrencePhysicalNumber occurrenceNumberPath [cmcp::q [cmcp::str $occurrenceNumberPath]] occurrenceNumberStatusCode $occurrenceNumberCode name [cmcp::q [cmcp::str $name]] flatNetId $flatId flatNetName [cmcp::q $flatName] isGlobal $global nativeNetPath [cmcp::q $netPath]]
            }
        } finally {delete_DboOccurrenceChildrenIter $it}
    }
    set phase child_iterator
    set it [$occ NewChildrenIter $state $::IterDefs_INSTS];cmcp::check $state
    try {
        for {set raw [$it NextOccurrence $state]} {$raw ne "NULL"} {set raw [$it NextOccurrence $state]} {
            cmcp::check $state
            cmcp::walk [DboOccurrenceToDboInstOccurrence $raw] $occ $segments [expr {$depth+1}] [linsert $ancestors end $occ]
        }
    } finally {delete_DboOccurrenceChildrenIter $it}
}
if {$argc!=3} {exit 2}
lassign $argv root design output
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error "no_design"}
    set ro [$d GetRootOccurrence $state];cmcp::check $state
    cmcp::walk $ro "" {} 0 {}
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj occurrenceCount $cmcp::count flatNetCount [dict size $cmcp::flatIds] pins [cmcp::arr $cmcp::rows]]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    set f [open "$output.error.json" {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj phase [cmcp::q $cmcp::phase] message [cmcp::q $message]]} finally {close $f}
    puts stderr "CADENCE_DBO_ERROR: phase=$cmcp::phase $message";exit 1
}
