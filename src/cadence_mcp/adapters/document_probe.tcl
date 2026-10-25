# Fixed DSN document lifecycle probe on fresh/owned copies only.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv install target output operation
if {$operation ni {create schematic_create schematic_rename schematic_delete page_delete}} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
set session "";set phase load;set refCount -1
set rc [catch {
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    if {$operation eq "create"} {
        if {[file exists $target]} {error existing_design}
        set phase create_design
        set d [$session CreateDesign $state [cmcp::cs $target] [cmcp::cs ROOT]];cmcp::check $state
        if {$d eq "NULL"} {error missing_design}
        set phase get_root
        set s [$d GetRootSchematic $state];cmcp::check $state
        if {$s eq "NULL"} {error missing_root}
        set phase create_page
        set p [$s NewPage $state [cmcp::cs PAGE_ONE]];cmcp::check $state
    } else {
        set phase open_design
        set d [$session GetDesignAndSchematics [cmcp::cs $target] $state];cmcp::check $state
        if {$d eq "NULL"} {error missing_design}
        if {$operation eq "schematic_create"} {
            set phase create_schematic
            set s [$d NewSchematic [cmcp::cs AUX] $state];cmcp::check $state
            if {$s eq "NULL"} {error missing_new_schematic}
            set phase create_page
            set p [$s NewPage $state [cmcp::cs AUX_PAGE]];cmcp::check $state
        } else {
            set phase get_aux
            set s [$d GetSchematic [cmcp::cs AUX] $state];cmcp::check $state
            if {$s eq "NULL"} {error missing_aux}
            set refCount [$s GetRefCount]
            if {$operation eq "schematic_rename"} {
                set phase rename_schematic
                cmcp::check [$s SetName [cmcp::cs AUX_RENAMED]]
            } elseif {$operation eq "schematic_delete"} {
                set phase delete_schematic
                cmcp::check [$d DeleteView $s]
                set s ""
            } else {
                set phase get_page
                set pi [$s NewPagesIter $state];cmcp::check $state
                set p [$pi NextPage $state];cmcp::check $state
                delete_DboSchematicPagesIter $pi
                if {$p eq "NULL"} {error no_aux_page}
                set phase delete_page
                cmcp::check [$s DeletePage $p]
                set p ""
            }
        }
    }
    if {[info exists p] && $p ne ""} {set phase save_page;cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]}
    if {$s ne ""} {set phase save_schematic;cmcp::check [$d SaveSchematic $s]}
    set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj caught $rc phase [cmcp::q $phase] operation [cmcp::q $operation] refCount $refCount message [cmcp::q [string range $message 0 2047]]]} finally {close $f}
if {$rc} {exit 1}
