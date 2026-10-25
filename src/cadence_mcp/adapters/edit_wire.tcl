# Fixed planned wire/alias addition on a new isolated output copy only.
source [file join [file dirname [info script]] json.tcl]
if {$argc<16} {exit 2}
lassign $argv root design output schematicName pageName operation ox1 oy1 ox2 oy2 oldNet x1 y1 x2 y2 aliasCount
if {$operation ni {set_endpoints delete} || ![string is integer -strict $aliasCount] || $aliasCount<0 || $aliasCount>32 || $argc!=16+5*$aliasCount} {exit 2}
set expectedAliases [dict create]
foreach {name ax ay nx ny} [lrange $argv 16 end] {
    set key [list $name $ax $ay]
    if {[dict exists $expectedAliases $key]} {exit 2}
    dict set expectedAliases $key [list $nx $ny]
}
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
    set state [DboState]
    set phase locate_wire
    set iterator [$page NewWiresIter $state];cmcp::check $state;set found {}
    try {
        for {set wire [$iterator NextWire $state]} {$wire ne "NULL"} {set wire [$iterator NextWire $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            if {[$wire GetPointCount $state]!=2} {cmcp::check $state;continue};cmcp::check $state
            set a [$wire GetPoint 0 $state];cmcp::check $state
            set b [$wire GetPoint 1 $state];cmcp::check $state
            set ax [DboTclHelper_sGetCPointX $a];set ay [DboTclHelper_sGetCPointY $a]
            set bx [DboTclHelper_sGetCPointX $b];set by [DboTclHelper_sGetCPointY $b]
            if {!(($ax==$ox1 && $ay==$oy1 && $bx==$ox2 && $by==$oy2) || ($ax==$ox2 && $ay==$oy2 && $bx==$ox1 && $by==$oy1))} {continue}
            set n [cmcp::cs ""];cmcp::check [$wire GetNetName $n]
            if {[cmcp::str $n] eq $oldNet} {lappend found $wire}
        }
    } finally {delete_DboPageWiresIter $iterator}
    if {[llength $found]!=1} {error ambiguous_wire}
    set wire [lindex $found 0];set scalar [DboWireToDboWireScalar $wire]
    if {$scalar eq "NULL"} {error not_scalar_wire}
    set state [DboState];set phase check_aliases
    set iterator [$wire NewAliasesIter $state];cmcp::check $state;set aliases {};set seen [dict create]
    try {
        for {set alias [$iterator NextAlias $state]} {$alias ne "NULL"} {set alias [$iterator NextAlias $state]} {
            cmcp::check $state
            if {[llength $aliases]>=32} {error alias_limit}
            set n [cmcp::cs ""];cmcp::check [$alias GetName $n]
            set p [$alias GetLocation $state];cmcp::check $state
            set key [list [cmcp::str $n] [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]
            if {![dict exists $expectedAliases $key] || [dict exists $seen $key]} {error alias_identity_mismatch}
            dict set seen $key 1
            lappend aliases [list $alias {*}[dict get $expectedAliases $key]]
        }
    } finally {delete_DboWireAliasesIter $iterator}
    if {[llength $aliases]!=$aliasCount} {error alias_count_mismatch}
    if {$operation eq "delete"} {
        set phase delete_wire;cmcp::check [$page DeleteWire $wire]
    } else {
        set phase set_wire_points
        cmcp::check [$scalar SetPoint 0 [DboTclHelper_sMakeCPoint $x1 $y1]]
        cmcp::check [$scalar SetPoint 1 [DboTclHelper_sMakeCPoint $x2 $y2]]
        set phase move_alias_anchors
        foreach entry $aliases {lassign $entry alias x y;cmcp::check [$alias SetLocation [DboTclHelper_sMakeCPoint $x $y]]}
    }
    set phase save_page
    cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
    set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q $operation] schematicName [cmcp::q $schematicName] pageName [cmcp::q $pageName]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
