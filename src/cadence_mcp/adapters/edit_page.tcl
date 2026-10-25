# Fixed create/rename page operation on one isolated output copy.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=7} {exit 2}
lassign $argv root design output operation schematicName oldName newName
if {$operation ni {create rename}} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error dbo_error}}
set session "";set phase opening
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error missing_design}
    set found {};set count 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set s [DboViewToDboSchematic $v];set n [cmcp::cs ""]; $s GetName $n
            if {[cmcp::str $n] eq $schematicName} {lappend found $s}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[llength $found]!=1} {error ambiguous_schematic}
    set s [lindex $found 0];set matches {};set phase checking_pages
    set pi [$s NewPagesIter $state];cmcp::check $state
    try {
        for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set n [cmcp::cs ""]; $p GetName $n;set name [cmcp::str $n]
            if {[string equal -nocase $name $newName]} {error page_name_conflict}
            if {$name eq $oldName} {lappend matches $p}
        }
    } finally {delete_DboSchematicPagesIter $pi}
    if {$operation eq "create"} {
        set phase create_page
        set p [$s NewPage $state [cmcp::cs $newName]];cmcp::check $state
        if {$p eq "NULL"} {error new_page_failed}
    } else {
        if {[llength $matches]!=1} {error ambiguous_page}
        set p [lindex $matches 0];set phase rename_page
        cmcp::check [$s Rename $p [cmcp::cs $newName]]
    }
    set phase mark_page;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p]
    set phase save_page;cmcp::check [$s SavePage $p]
    set phase save_schematic;cmcp::check [$d SaveSchematic $s]
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj saved true operation [cmcp::q $operation] schematicName [cmcp::q $schematicName] name [cmcp::q $newName]]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    catch {set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f}
    exit 1
}
