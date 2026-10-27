# Explicit bReturnShared=1: retain each unit shared-pin definition row.
# Self-authored, read-only Capture design-definition inspection.
# argv: installRoot copiedDSN resultJSON maxObjects
# No client script, eval, save, mutation, GUI command or server socket is accepted.
namespace eval cmcp {variable count 0; variable limit 100000}
source [file join [file dirname [info script]] .. src cadence_mcp adapters json.tcl]
source [file join [file dirname [info script]] .. src cadence_mcp adapters dbo_pin_net.tcl]
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
    set schematics {}; set pages {}; set parts {}; set pins {};set memberships {}
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
                    set busnets {};set seenBus {};set ws [DboState];set wit [$p NewWiresIter $ws];cmcp::check $ws
                    try {
                     for {set w [$wit NextWire $ws]} {$w ne "NULL"} {set w [$wit NextWire $ws]} {
                      cmcp::check $ws;cmcp::tick
                      if {[$w GetObjectType]!=$::DboBaseObject_WIRE_BUS} {continue}
                      set wn [$w GetNet $ws];cmcp::check $ws
                      if {$wn eq "NULL"} {error missing_bus_net}
                      if {[dict exists $seenBus $wn]} {continue};dict set seenBus $wn 1
                      set bn [DboNetToDboNetBus $wn];set name [cmcp::cs ""];cmcp::check [$bn GetNetName $name]
                      lappend busnets [list $bn [cmcp::str $name]]
                     }
                    } finally {delete_DboPageWiresIter $wit}
                    set it [$p NewPartInstsIter $state]; cmcp::check $state
                    try {
                        set oi 0
                        for {set o [$it NextPartInst $state]} {$o ne "NULL"} {set o [$it NextPartInst $state]} {
                            cmcp::check $state; cmcp::tick
                            set oid "$pageId/part-[incr oi]"
                            set ref [cmcp::cs ""]; $o GetReference $ref
                            set ref [cmcp::str $ref]
                            lappend parts [cmcp::obj objectId [cmcp::q $oid] pageId [cmcp::q $pageId] schematicId [cmcp::q $sid] reference [cmcp::q $ref]]
                            set pit [$o NewPinsIter $state $::IterDefs_ALL 1]; cmcp::check $state
                            try {
                                set ni 0
                                for {set pin [$pit NextPin $state]} {$pin ne "NULL"} {set pin [$pit NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    set number [cmcp::cs ""]; $pin GetPinNumber $number
                                    set name [cmcp::cs ""]; $pin GetPinName $name
                                    lassign [cmcp::pin_net $pin] hasNet netName
                                    set pnState [DboState];set pn [$pin GetNet $pnState]
                                    if {$pn eq "NULL"} {if {[$pnState Failed] && [$pnState Code]!=1021} {cmcp::check $pnState}} else {cmcp::check $pnState}
                                    foreach busrow $busnets {
                                     cmcp::tick;lassign $busrow bn bname;set member false;set pos -1;set same false
                                     if {$pn ne "NULL"} {
                                      set raw [$bn HasMember $pn]
                                      if {$raw!=0 && $raw!=1} {error invalid_has_member}
                                      if {$raw} {
                                       set member true;set pos [$bn GetPosition $pn]
                                       if {$pos<0} {error invalid_member_position}
                                       set memberState [DboState];set mn [$bn GetMember $pos $memberState];cmcp::check $memberState
                                       if {$mn ne $pn} {error member_pointer_mismatch};set same true
                                      }
                                     }
                                     lappend memberships [cmcp::obj pageId [cmcp::q $pageId] reference [cmcp::q $ref] pinNumber [cmcp::q [cmcp::str $number]] busName [cmcp::q $bname] pinNet [cmcp::q $netName] hasMember $member position $pos memberPointerEqualsPinNet $same]
                                    }

                                    lappend pins [cmcp::obj objectId [cmcp::q "$oid/pin-[incr ni]"] partId [cmcp::q $oid] pageId [cmcp::q $pageId] schematicId [cmcp::q $sid] reference [cmcp::q $ref] number [cmcp::q [cmcp::str $number]] name [cmcp::q [cmcp::str $name]] connected $hasNet net [cmcp::q $netName]]
                                }
                            } finally {delete_DboPartInstPinsIter $pit}
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set json [cmcp::obj schematic [cmcp::arr $schematics] page [cmcp::arr $pages] part [cmcp::arr $parts] pin [cmcp::arr $pins] memberships [cmcp::arr $memberships]]
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf; puts -nonewline $f $json} finally {close $f}
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: $message"; exit 1}
