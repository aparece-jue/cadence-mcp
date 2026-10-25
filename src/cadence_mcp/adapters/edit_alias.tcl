# Fixed JSON scalar alias edit/delete on a new owned design copy only.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root design specPath output
if {[file size $specPath]>65536} {exit 2}
set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
foreach key {schematicName pageName wireNativeId oldPoints oldNet aliasName oldLocation operation name location} {set $key [dict get $spec $key]}
if {$operation ni {set delete}} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
set session "";set phase load_dll
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set phase open_design
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error missing_design}
    set phase locate_page
    set matches {};set count 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set view [$vi NextView $state]} {$view ne "NULL"} {set view [$vi NextView $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set schematic [DboViewToDboSchematic $view];set sn [cmcp::cs ""];cmcp::check [$schematic GetName $sn]
            if {[cmcp::str $sn] ne $schematicName} {continue}
            set pi [$schematic NewPagesIter $state];cmcp::check $state
            try {
                for {set page [$pi NextPage $state]} {$page ne "NULL"} {set page [$pi NextPage $state]} {
                    cmcp::check $state
                    if {[incr count]>100000} {error object_limit}
                    set pn [cmcp::cs ""];cmcp::check [$page GetName $pn]
                    if {[cmcp::str $pn] eq $pageName} {lappend matches [list $schematic $page]}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[llength $matches]!=1} {error ambiguous_page}
    lassign [lindex $matches 0] schematic page
    set state [DboState];set phase locate_wire
    set iterator [$page NewWiresIter $state];cmcp::check $state;set found {};set count 0
    try {
        for {set wire [$iterator NextWire $state]} {$wire ne "NULL"} {set wire [$iterator NextWire $state]} {
            cmcp::check $state;if {[incr count]>100000} {error object_limit}
            if {[$wire GetId $state]!=$wireNativeId} {cmcp::check $state;continue};cmcp::check $state
            set n [$wire GetPointCount $state];cmcp::check $state
            if {$n<2 || $n>256 || $n!=[llength $oldPoints]} {error wire_shape_changed}
            set pts {}
            for {set i 0} {$i<$n} {incr i} {
                set p [$wire GetPoint $i $state];cmcp::check $state
                lappend pts [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]
            }
            if {$pts ne $oldPoints && [lreverse $pts] ne $oldPoints} {error wire_points_changed}
            set n [cmcp::cs ""];cmcp::check [$wire GetNetName $n]
            if {[cmcp::str $n] ne $oldNet} {error wire_net_changed}
            lappend found $wire
        }
    } finally {delete_DboPageWiresIter $iterator}
    if {[llength $found]!=1} {error ambiguous_wire}
    set wire [lindex $found 0]
    if {[DboWireToDboWireScalar $wire] eq "NULL"} {error not_scalar_wire}
    set phase locate_alias;set state [DboState];set iterator [$wire NewAliasesIter $state];cmcp::check $state;set found {}
    try {
        for {set alias [$iterator NextAlias $state]} {$alias ne "NULL"} {set alias [$iterator NextAlias $state]} {
            cmcp::check $state;if {[incr count]>100000} {error object_limit}
            set n [cmcp::cs ""];cmcp::check [$alias GetName $n]
            set p [$alias GetLocation $state];cmcp::check $state
            set xy [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]
            if {[cmcp::str $n] eq $aliasName && $xy eq $oldLocation} {lappend found $alias}
        }
    } finally {delete_DboWireAliasesIter $iterator}
    if {[llength $found]!=1} {error ambiguous_alias}
    set alias [lindex $found 0];set phase mutate_alias
    if {$operation eq "delete"} {cmcp::check [$wire DeleteAlias $alias]} else {
        cmcp::check [$alias SetName [cmcp::cs $name]]
        cmcp::check [$alias SetLocation [DboTclHelper_sMakeCPoint {*}$location]]
    }
    set phase save_page;cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
    set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q $operation]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f $result;close $f
if {$rc} {exit 1}
