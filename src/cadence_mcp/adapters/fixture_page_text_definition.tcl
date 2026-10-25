# Fixed comment-text creation/read on an owned DSN copy; no electrical mutation.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=13} {exit 2}
lassign $argv root design output schematicName pageName x y width height text operation rotation mirror
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
proc cmcp::pt {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
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
    if {$operation eq "add"} {
        set phase create_font
        set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
        set phase create_comment_text
        set comment [$page NewGraphicCommentTextInst $state [DboTclHelper_sMakeCRect 0 0 $width $height] [DboTclHelper_sMakeCPoint $x $y] [cmcp::cs $text] $font $rotation];cmcp::check $state
        if {$comment eq "NULL"} {error comment_missing}
        set phase set_text_definition
        set raw [$comment GetDboCommentText]
        if {$raw eq "NULL"} {error text_definition_missing}
        cmcp::check [$raw SetBoundingBox [DboTclHelper_sMakeCRect $x $y [expr {$x+$width}] [expr {$y+$height}]]]
        cmcp::check [$raw SetLocation [DboTclHelper_sMakeCPoint $x $y]]
        cmcp::check [$comment SetMirror $mirror]
        set phase save_page
        cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
        set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
        set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
        set result [cmcp::obj saved true operation [cmcp::q add_comment_text]]
    } elseif {$operation eq "read"} {
        set phase read_comment_texts
        set rows {};set n 0
        set gi [$page NewCommentGraphicsIter $state];cmcp::check $state
        try {
            for {set obj [$gi NextCommentGraphic $state]} {$obj ne "NULL"} {set obj [$gi NextCommentGraphic $state]} {
                cmcp::check $state
                if {[incr n]>100000} {error object_limit}
                if {[$obj GetObjectType] != $::DboBaseObject_GRAPHIC_COMMENTTEXT_INST} {continue}
                set comment [DboGraphicInstanceToDboGraphicCommentTextInst $obj]
                set def [$comment GetDboCommentText]
                if {$def eq "NULL"} {error text_definition_missing}
                set value [cmcp::cs ""];cmcp::check [$def GetText $value]
                set location [$comment GetLocation $state];cmcp::check $state
                set rotation [$comment GetRotation $state];cmcp::check $state
                set mirror [$comment GetMirror $state];cmcp::check $state
                set font [$def GetFont $state];cmcp::check $state
                set name [cmcp::cs ""];DboTclHelper_sGetLFName $font $name
                set attrs [list name [cmcp::q [cmcp::str $name]]]
                foreach field {Height Width Escapement Orientation Weight Italic Underline StrikeOut CharSet OutPrecision ClipPrecision Quality PitchAndFamily} {
                    lappend attrs $field [DboTclHelper_sGetLF$field $font]
                }
                lappend rows [cmcp::obj text [cmcp::q [cmcp::str $value]] location [cmcp::pt $location] rotationCode $rotation mirrorCode $mirror font [cmcp::obj {*}$attrs]]
            }
        } finally {delete_DboPageCommentGraphicsIter $gi}
        set result [cmcp::obj texts [cmcp::arr $rows]]
    } else {error invalid_operation}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
