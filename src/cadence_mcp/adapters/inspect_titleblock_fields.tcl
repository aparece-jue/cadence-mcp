# Read native titleblock fields and independent owner page context.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
if {$argc != 6} {exit 2}
lassign $argv root design output schematicName pageName nativeId
if {![string is integer -strict $nativeId] || $nativeId < 0 || $nativeId > 4294967295} {exit 2}
proc cmcp::cs {value} {DboTclHelper_sMakeCString $value}
proc cmcp::str {value} {DboTclHelper_sGetConstCharPtr $value}
proc cmcp::check {state} {if {[$state Failed]} {error "dbo_[$state Code]"}}
proc cmcp::rect {value} {
    set a [DboTclHelper_sGetCRectTopLeft $value]
    set b [DboTclHelper_sGetCRectBottomRight $value]
    return [cmcp::arr [list [DboTclHelper_sGetCPointX $a] [DboTclHelper_sGetCPointY $a] [DboTclHelper_sGetCPointX $b] [DboTclHelper_sGetCPointY $b]]]
}
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set designObj [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$designObj eq "NULL"} {error missing_design}
    lassign [cmcp::qualifiedPage $designObj $schematicName $pageName] schematic page
    set title [$page GetTitleBlock $nativeId $state];cmcp::check $state
    if {$title eq "NULL" || [$title GetId $state] != $nativeId} {error titleblock_identity}
    cmcp::check $state
    set fields [list nativeId $nativeId]
    foreach {key method} {name GetName designName GetDesignName designFileName GetDesignFileName
                          sourceSymbol GetSourceSymbolName pageSize GetPageSize} {
        set value [cmcp::cs ""];cmcp::check [$title $method $value]
        lappend fields $key [cmcp::q [cmcp::str $value]]
    }
    foreach {key method} {pageCount GetPageCount pageNumber GetPageNumber} {
        set value [$title $method $state];cmcp::check $state
        lappend fields $key $value
    }
    set number [$page GetPageNumber $state];cmcp::check $state
    set size [cmcp::cs ""];cmcp::check [$page GetSizeName $size]
    lappend fields ownerPageNumber $number ownerSizeName [cmcp::q [cmcp::str $size]]
    # Observe the native cache without setting dirty flags or manufacturing bounds.
    set state [DboState]
    set symbol [$title GetSymbol $state];cmcp::check $state
    if {$symbol eq "NULL"} {error missing_titleblock_symbol}
    set state [DboState]
    set offset [$title GetOffsetBoundingBox $state];cmcp::check $state
    lappend fields boundingBoxObservation [cmcp::obj localBounds [cmcp::rect [$title GetBoundingBox]] offsetBounds [cmcp::rect $offset] symbolBounds [cmcp::rect [$symbol GetBoundingBox]] dirty [$title IsBoundingBoxDirty]]
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj {*}$fields]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: titleblock fields: $message";exit 1}
