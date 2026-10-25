# Fixed planned wire/alias addition on a new isolated output copy only.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=12} {exit 2}
lassign $argv root design output schematicName pageName x1 y1 x2 y2 aliasName ax ay
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
    set phase create_wire
    set wire [$page NewWireScalar $state [DboTclHelper_sMakeCPoint $x1 $y1] [DboTclHelper_sMakeCPoint $x2 $y2]];cmcp::check $state
    if {$wire eq "NULL"} {error wire_missing}
    set phase create_font
    set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
    set phase create_alias
    set alias [$wire NewAlias $state [cmcp::cs $aliasName] [DboTclHelper_sMakeCPoint $ax $ay] $font 0 0];cmcp::check $state
    if {$alias eq "NULL"} {error alias_missing}
    set phase save_page
    cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
    set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q add_wire] schematicName [cmcp::q $schematicName] pageName [cmcp::q $pageName]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
