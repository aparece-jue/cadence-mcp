# Read-only occurrence structure and effective component-instance properties.
# argv: installRoot copiedDSN outputJSON
source [file join [file dirname [info script]] json.tcl]
namespace eval cmcp {variable rows {}; variable count 0; variable totalProperties 0; variable textBytes 0}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error"}}
proc cmcp::boundedText {value limit} {
    variable textBytes
    if {[string length $value] > $limit} {error "hierarchy_string_limit"}
    incr textBytes [string length [encoding convertto utf-8 $value]]
    if {$textBytes > 8388608} {error "hierarchy_text_limit"}
    return $value
}
proc cmcp::definitionBudget {name edges ancestors memoName} {
    upvar 1 $memoName memo
    if {$name in $ancestors} {error recursive_hierarchy}
    if {[llength $ancestors] > 64} {error hierarchy_depth_limit}
    if {[dict exists $memo $name]} {return [dict get $memo $name]}
    set height 0
    set occurrences 1
    foreach child [dict get $edges $name] {
        if {![dict exists $edges $child]} {continue}
        lassign [cmcp::definitionBudget $child $edges [linsert $ancestors end $name] memo] childHeight childCount
        set height [expr {max($height, 1 + $childHeight)}]
        incr occurrences $childCount
        if {$occurrences > 10000} {error hierarchy_occurrence_limit}
    }
    set value [list $height $occurrences]
    dict set memo $name $value
    return $value
}
proc cmcp::checkIteratorEnd {state} {
    if {[$state Failed] && [$state Code] != 1022} {error "unexpected_definition_iterator_end_[$state Code]"}
}
proc cmcp::checkLocalDefinitions {design} {
    set st [DboState];set root [$design GetRootSchematic $st];cmcp::check $st
    if {$root eq "NULL"} {error no_hierarchy_root}
    set rootName [cmcp::cs ""];cmcp::check [$root GetName $rootName]
    set edges {};set definitions 0
    set ts [DboState];set name [cmcp::cs ""];set lib [cmcp::cs ""];set target [cmcp::cs ""]
    set vi [$design NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st
    if {$vi eq "NULL"} {error missing_definition_iterator}
    try {
        for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
            cmcp::check $st
            set s [DboViewToDboSchematic $view]
            cmcp::check [$s GetName $name]
            set key [string tolower [cmcp::str $name]]
            if {[dict exists $edges $key]} {error ambiguous_schematic_definition}
            if {[incr definitions] > 100000} {error hierarchy_definition_limit}
            dict set edges $key {}
            set ps [DboState];set pi [$s NewPagesIter $ps];cmcp::check $ps
            if {$pi eq "NULL"} {error missing_definition_page_iterator}
            try {
                for {set p [$pi NextPage $ps]} {$p ne "NULL"} {set p [$pi NextPage $ps]} {
                    cmcp::check $ps
                    if {[incr definitions] > 100000} {error hierarchy_definition_limit}
                    set os [DboState];set oi [$p NewPartInstsIter $os];cmcp::check $os
                    if {$oi eq "NULL"} {error missing_definition_part_iterator}
                    try {
                        for {set part [$oi NextPartInst $os]} {$part ne "NULL"} {set part [$oi NextPartInst $os]} {
                            cmcp::check $os
                            if {[incr definitions] > 100000} {error hierarchy_definition_limit}
                            set type [$part GetContentsViewType $ts];cmcp::check $ts
                            # SPB 24.1 local schematic implementation code.
                            if {$type != 1 || [$part IsExternalDesignPart]} {continue}
                            cmcp::check [$part GetContentsLibName $lib]
                            if {[cmcp::str $lib] ne ""} {continue}
                            cmcp::check [$part GetContentsViewName $target]
                            dict lappend edges $key [string tolower [cmcp::str $target]]
                        }
                    } finally {delete_DboPagePartInstsIter $oi}
                    cmcp::checkIteratorEnd $os
                }
            } finally {delete_DboSchematicPagesIter $pi}
            cmcp::checkIteratorEnd $ps
        }
    } finally {delete_DboLibViewsIter $vi}
    cmcp::checkIteratorEnd $st
    set key [string tolower [cmcp::str $rootName]]
    if {![dict exists $edges $key]} {error no_hierarchy_root}
    set memo {}
    lassign [cmcp::definitionBudget $key $edges {} memo] height _
    if {$height > 64} {error hierarchy_depth_limit}
}
proc cmcp::walk {occ parent depth ancestors} {
    variable rows; variable count; variable totalProperties
    if {$occ eq "NULL"} {error missing_native_occurrence}
    if {$occ in $ancestors} {error recursive_hierarchy}
    if {$depth > 64} {error hierarchy_depth_limit}
    if {$count >= 10000} {error hierarchy_occurrence_limit}
    set state [DboState]
    set recursive [$occ IsRecursive $state]; cmcp::check $state
    if {$recursive} {error "recursive_hierarchy"}
    set id "occ-[incr count]"
    set path [cmcp::cs ""]; cmcp::check [$occ GetPathName $path]
    set hierPath [cmcp::cs ""]; cmcp::check [$occ GetHierPathName $hierPath]
    set pathText [cmcp::boundedText [cmcp::str $path] 16384]
    set hierPathText [cmcp::boundedText [cmcp::str $hierPath] 16384]
    set reference [cmcp::cs ""]
    set properties {}
    # The root is a design context, not a placed component reference.
    if {$depth > 0} {
        cmcp::check [$occ GetReferenceDesignator $reference]
        set pi [$occ NewEffectivePropsIter $state]; cmcp::check $state
        if {$pi eq "NULL"} {error "missing_effective_iterator"}
        try {
            set name [cmcp::cs ""]; set value [cmcp::cs ""]
            set valueType [DboTclHelper_sMakeDboValueType]
            set editable [DboTclHelper_sMakeInt]
            while {1} {
                set next [$pi NextEffectiveProp $name $value $valueType $editable]
                if {[$next OK] != 1} {
                    if {[$next Code] != 1022} {error "unexpected_effective_end_[$next Code]"}
                    break
                }
                if {[llength $properties] >= 512 || [incr totalProperties] > 100000} {error "property_limit"}
                set propName [cmcp::boundedText [cmcp::str $name] 256]
                if {$propName eq ""} {error "empty_property_name"}
                set propValue [cmcp::boundedText [cmcp::str $value] 16384]
                lappend properties [cmcp::obj name [cmcp::q $propName] value [cmcp::q $propValue]]
            }
        } finally {delete_DboEffectivePropsIter $pi}
    }
    set referenceText [cmcp::boundedText [cmcp::str $reference] 256]
    lappend rows [cmcp::obj occurrenceId [cmcp::q $id] parentId [expr {$parent eq "" ? "null" : [cmcp::q $parent]}] depth $depth path [cmcp::q $pathText] hierarchicalPath [cmcp::q $hierPathText] reference [cmcp::q $referenceText] properties [cmcp::arr $properties]]
    set it [$occ NewChildrenIter $state $::IterDefs_INSTS]; cmcp::check $state
    if {$it eq "NULL"} {error "missing_child_iterator"}
    try {
        for {set child [$it NextOccurrence $state]} {$child ne "NULL"} {set child [$it NextOccurrence $state]} {
            cmcp::check $state
            cmcp::walk [DboOccurrenceToDboInstOccurrence $child] $id [expr {$depth + 1}] [linsert $ancestors end $occ]
        }
    } finally {delete_DboOccurrenceChildrenIter $it}
    if {[$state Failed] && [$state Code] != 1022} {error "unexpected_child_end_[$state Code]"}
}
if {$argc != 3} {exit 2}
lassign $argv root design output
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state]; cmcp::check $state
    if {$d eq "NULL"} {error "no_design"}
    cmcp::checkLocalDefinitions $d
    set rootOccurrence [$d GetRootOccurrence $state]; cmcp::check $state
    if {$rootOccurrence eq "NULL"} {error "no_hierarchy_root"}
    cmcp::walk $rootOccurrence "" 0 {}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $stream -encoding utf-8 -translation lf; puts -nonewline $stream [cmcp::arr $cmcp::rows]} finally {close $stream}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    switch -- $message {
        recursive_hierarchy {puts stderr "CADENCE_HIERARCHY_INCOMPLETE:cycle"}
        no_hierarchy_root {puts stderr "CADENCE_HIERARCHY_INCOMPLETE:missing_root"}
        hierarchy_depth_limit - hierarchy_occurrence_limit - hierarchy_definition_limit -
        hierarchy_string_limit - hierarchy_text_limit - property_limit {
            puts stderr "CADENCE_HIERARCHY_INCOMPLETE:resource_limit"
        }
    }
    puts stderr "CADENCE_DBO_ERROR: hierarchy inspection failed: $message"
    exit 1
}
