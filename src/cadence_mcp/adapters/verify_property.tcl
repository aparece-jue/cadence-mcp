# argv: installRoot DSN outputJSON schematicName pageName reference
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] property_api.tcl]
if {$argc != 6} {exit 2}
lassign $argv root design output schematicName pageName reference
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set object [$session GetDesignAndSchematics [::cmcpProperty::cs $design] $state]
    ::cmcpProperty::check $state
    lassign [::cmcpProperty::find $object $schematicName $pageName $reference] schematic page part
    lassign [::cmcpProperty::read $part] exists value
    set stream [open $output {WRONLY CREAT EXCL}]
    try {
        fconfigure $stream -encoding utf-8 -translation lf
        puts $stream [cmcp::obj exists [expr {$exists ? "true" : "false"}] value [cmcp::q $value]]
    } finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: fixed property verification failed";exit 1}
