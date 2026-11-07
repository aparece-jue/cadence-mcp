# Fixed schematic lifecycle worker for the isolated copy owned by a planned task.
source [file join [file dirname [info script]] json.tcl]
if {$argc != 7} {exit 2}
lassign $argv install design output operation schematicName newName pageName
if {$operation ni {create rename delete}} {exit 2}
proc cmcp::cs {value} {return [DboTclHelper_sMakeCString $value]}
proc cmcp::name {object} {
    set text [cmcp::cs ""]
    cmcp::check [$object GetName $text]
    return [DboTclHelper_sGetConstCharPtr $text]
}
proc cmcp::check {state} {
    if {[$state Failed]} {error "dbo_[$state Code]"}
}
set session ""
set phase load
set rc [catch {
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set phase open
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]; cmcp::check $state
    if {$d eq "NULL"} {error missing_design}
    set root [$d GetRootSchematic $state]; cmcp::check $state
    if {$root eq "NULL"} {error missing_root}
    if {$operation eq "create"} {
        set phase create_schematic
        set s [$d NewSchematic [cmcp::cs $newName] $state]; cmcp::check $state
        if {$s eq "NULL"} {error missing_schematic}
        set phase create_page
        set p [$s NewPage $state [cmcp::cs $pageName]]; cmcp::check $state
        if {$p eq "NULL"} {error missing_page}
        cmcp::check [$p MarkModified]
        cmcp::check [$s MarkModified $p]
        cmcp::check [$s SavePage $p]
    } else {
        set phase select_schematic
        set s [$d GetSchematic [cmcp::cs $schematicName] $state]; cmcp::check $state
        if {$s eq "NULL" || [cmcp::name $s] ne $schematicName} {error target_schematic_changed}
        if {[string equal -nocase [cmcp::name $root] $schematicName]} {error root_schematic_protected}
        if {$operation eq "rename"} {
            set phase rename_schematic
            cmcp::check [$s SetName [cmcp::cs $newName]]
        } else {
            set phase delete_schematic
            cmcp::check [$d DeleteView $s]
            set s ""
        }
    }
    set phase save
    if {$s ne ""} {cmcp::check [$d SaveSchematic $s]}
    cmcp::check [$session MarkAllLibForSave $d]
    cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]
} else {
    set result [cmcp::obj saved true operation [cmcp::q $operation] schematicName [cmcp::q $schematicName] name [cmcp::q $newName]]
}
set stream [open $output {WRONLY CREAT EXCL}]
try {fconfigure $stream -encoding utf-8 -translation lf; puts $stream $result} finally {close $stream}
if {$rc} {exit 1}
