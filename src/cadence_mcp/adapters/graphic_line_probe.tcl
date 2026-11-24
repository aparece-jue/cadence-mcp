# Fixed graphic-line operation on an owned DSN copy; no electrical wire mutation.
source [file join [file dirname [info script]] json.tcl]
if {$argc ni {10 12 13}} {exit 2}
lassign $argv root design output schematicName pageName x1 y1 x2 y2 operation
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
        set phase create_graphic_line
        set line [$page NewGraphicLineInst $state [DboTclHelper_sMakeCPoint 0 0] [DboTclHelper_sMakeCPoint [expr {$x2-$x1}] [expr {$y2-$y1}]] [DboTclHelper_sMakeCPoint $x1 $y1] 0];cmcp::check $state
        if {$line eq "NULL"} {error line_missing}
        if {$argc>=12} {
            lassign [lrange $argv 10 11] style width
            if {![string is integer -strict $style] || $style<0 || $style>5 || ![string is integer -strict $width] || $width<0 || $width>3} {error invalid_stroke}
            set definition [$line GetDboLine]
            cmcp::check [$definition SetLineStyle $style]
            cmcp::check [$definition SetLineWidth $width]
        }
        if {$argc==13} {
            set color [lindex $argv 12]
            if {![string is integer -strict $color] || $color<1 || $color>48} {error invalid_color}
            set owner [$definition GetOwner]
            if {$owner eq "NULL"} {error line_owner_missing}
            cmcp::check [DboGraphicObject_sSetColor $owner $color]
            cmcp::check [$line SetColor $color]
        }
        set phase save_page
        cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page];cmcp::check [$schematic SavePage $page]
        set phase save_schematic;cmcp::check [$d SaveSchematic $schematic]
        set phase save_design;cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
        set result [cmcp::obj saved true operation [cmcp::q add_graphic_line]]
    } elseif {$operation in {read read_styled read_colored}} {
        set phase read_graphic_lines
        set rows {};set n 0
        set gi [$page NewCommentGraphicsIter $state];cmcp::check $state
        try {
            for {set obj [$gi NextCommentGraphic $state]} {$obj ne "NULL"} {set obj [$gi NextCommentGraphic $state]} {
                cmcp::check $state
                if {[incr n]>100000} {error object_limit}
                if {[$obj GetObjectType] != $::DboBaseObject_GRAPHIC_LINE_INST} {continue}
                set line [DboGraphicInstanceToDboGraphicLineInst $obj]
                set def [$line GetDboLine]
                if {$def eq "NULL"} {error line_definition_missing}
                set start [$def GetStart $state];cmcp::check $state
                set end [$def GetEnd $state];cmcp::check $state
                set location [$line GetLocation $state];cmcp::check $state
                set rotation [$line GetRotation $state];cmcp::check $state
                set mirror [$line GetMirror $state];cmcp::check $state
                set a [$line GetOffsetGraphicPoint $start];set b [$line GetOffsetGraphicPoint $end]
                set stroke {}
                if {$operation in {read_styled read_colored}} {
                    set style [$def GetLineStyle $state];cmcp::check $state
                    set width [$def GetLineWidth $state];cmcp::check $state
                    set stroke [list lineStyle $style lineWidth $width]
                }
                if {$operation eq "read_colored"} {
                    set color [$line GetColor $state];cmcp::check $state
                    set owner [$def GetOwner]
                    if {$owner eq "NULL"} {error line_owner_missing}
                    set definitionColor [DboGraphicObject_sGetColor $owner $state];cmcp::check $state
                    lappend stroke lineColor $color definitionColor $definitionColor
                }
                lappend rows [cmcp::obj {*}$stroke localStart [cmcp::pt $start] localEnd [cmcp::pt $end] location [cmcp::pt $location] start [cmcp::pt $a] end [cmcp::pt $b] rotationCode $rotation mirrorCode $mirror]
            }
        } finally {delete_DboPageCommentGraphicsIter $gi}
        set result [cmcp::obj lines [cmcp::arr $rows]]
    } else {error invalid_operation}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
