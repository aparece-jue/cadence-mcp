# Self-authored, read-only wire geometry inspection; no rendering or PDF.
# argv: installRoot copiedDSN resultJSON maxObjects
# No client script, eval, save, mutation, GUI command or server socket is accepted.
namespace eval cmcp {variable count 0; variable limit 100000}
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::str {value} {return [DboTclHelper_sGetConstCharPtr $value]}
proc cmcp::check {state} {if {[$state Failed]} {error "DboState failure"}}
proc cmcp::tick {} {
    variable count; variable limit
    incr count
    if {$count > $limit} {error "Object limit exceeded; traversal incomplete"}
}
if {$argc != 4} {puts stderr "Invalid inspector arguments"; exit 2}
lassign $argv root design output maxObjects
set cmcp::limit $maxObjects
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]
    cmcp::check $state
    if {$d eq "NULL"} {error "No design"}
    set schematics {}; set pages {}; set wires {}
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS]; cmcp::check $state
    try {
        set si 0
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            cmcp::check $state; cmcp::tick
            set s [DboViewToDboSchematic $v]
            set name [cmcp::cs ""]; $s GetName $name
            set sid "schematic-[incr si]"
            lappend schematics [cmcp::obj objectId [cmcp::q $sid] name [cmcp::q [cmcp::str $name]]]
            set pi [$s NewPagesIter $state]; cmcp::check $state
            try {
                set pn 0
                for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
                    cmcp::check $state; cmcp::tick
                    set pageId "$sid/page-[incr pn]"
                    set name [cmcp::cs ""]; $p GetName $name
                    lappend pages [cmcp::obj objectId [cmcp::q $pageId] schematicId [cmcp::q $sid] name [cmcp::q [cmcp::str $name]]]
                    set it [$p NewWiresIter $state]; cmcp::check $state
                    try {
                        set wi 0
                        for {set wire [$it NextWire $state]} {$wire ne "NULL"} {set wire [$it NextWire $state]} {
                            cmcp::check $state; cmcp::tick
                            set points {}; set junctions {}
                            set n [$wire GetPointCount $state]; cmcp::check $state
                            if {$n < 2 || $n > 10000} {error "Invalid or unsupported wire point count"}
                            for {set ix 0} {$ix < $n} {incr ix} {
                                cmcp::tick
                                set point [$wire GetPoint $ix $state]; cmcp::check $state
                                set x [DboTclHelper_sGetCPointX $point]
                                set y [DboTclHelper_sGetCPointY $point]
                                lappend points [cmcp::arr [list $x $y]]
                            }
                            set name [cmcp::cs ""]; cmcp::check [$wire GetNetName $name]
                            set nativeId [$wire GetId $state]; cmcp::check $state
                            lappend wires [cmcp::obj objectId [cmcp::q "$pageId/wire-[incr wi]"] pageId [cmcp::q $pageId] nativeId $nativeId objectType [$wire GetObjectType] net [cmcp::q [cmcp::str $name]] points [cmcp::arr $points]]
                        }
                    } finally {delete_DboPageWiresIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set json [cmcp::obj schematic [cmcp::arr $schematics] page [cmcp::arr $pages] wire [cmcp::arr $wires]]
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf; puts -nonewline $f $json} finally {close $f}
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: $message"; exit 1}
