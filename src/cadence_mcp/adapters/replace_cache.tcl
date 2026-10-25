# Fixed new-copy source-qualified replacement with explicit reference/string override restoration.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv install design request output
if {[file size $request]>524288} {exit 2}
set f [open $request];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 524289]]} finally {close $f}
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
proc cmcp::instanceProperties {part} {
    set st [DboState];set it [$part NewUserPropsIter $st];cmcp::check $st;set result {}
    try {
        for {set prop [$it NextUserProp $st]} {$prop ne "NULL"} {set prop [$it NextUserProp $st]} {
            cmcp::check $st
            if {[dict size $result]>=512} {error property_limit}
            set name [cmcp::cs ""];cmcp::check [$prop GetName $name];set name [cmcp::str $name]
            if {[dict exists $result $name]} {error duplicate_user_property}
            dict set result $name $prop
        }
    } finally {delete_DboUserPropsIter $it}
    if {[$st Failed] && [$st Code]!=1022} {error unexpected_user_property_end}
    return $result
}
proc cmcp::restoreUsers {part wanted} {
    set current [cmcp::instanceProperties $part];set names {}
    foreach row $wanted {
        if {[dict get $row nativeType]!=0} {error typed_override_unaccepted}
        set name [dict get $row name];lappend names $name
    }
    dict for {name prop} $current {
        if {$name ni $names} {
            if {![$prop IsDeletable]} {error extra_locked_user_property}
            cmcp::check [$part DeleteUserProp [cmcp::cs $name]]
        }
    }
    foreach row $wanted {
        set name [dict get $row name];set value [dict get $row value]
        if {[dict exists $current $name]} {
            set prop [dict get $current $name];set st [DboState];set type [$prop GetType $st];cmcp::check $st
            set old [cmcp::cs ""];cmcp::check [$prop GetStringValue $old]
            if {$type!=0} {error wrong_user_property_type}
            if {[cmcp::str $old] ne $value} {
                if {![$prop IsEditable]} {error locked_user_property}
                cmcp::check [$prop SetStringValue [cmcp::cs $value]]
            }
        } else {
            set st [DboState];set prop [$part NewUserProp [cmcp::cs $name] [cmcp::cs $value] $st];cmcp::check $st
            if {$prop eq "NULL"} {error missing_new_user_property}
        }
    }
}
set session "";set phase opening
set rc [catch {
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set st [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
    set library [$session GetLibAndSchematics [cmcp::cs [dict get $spec newLib]] $st];cmcp::check $st
    if {$d eq "NULL" || $library eq "NULL"} {error missing_input}
    set cached [$d GetCachedPackage [cmcp::cs [dict get $spec oldLib]] [cmcp::cs [dict get $spec oldName]]]
    if {$cached eq "NULL"} {error source_cache_missing}
    set changes [dict get $spec changes];set mappings {}
    if {[llength $changes]<1 || [llength $changes]>64} {error change_limit}
    foreach row $changes {
        set id [dict get $row nativeId]
        if {![string is integer -strict $id] || [dict exists $mappings $id]} {error duplicate_native_identity}
        dict set mappings $id $row
    }
    set pages {};set count 0;set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st
    try {
        for {set v [$vi NextView $st]} {$v ne "NULL"} {set v [$vi NextView $st]} {
            cmcp::check $st;set s [DboViewToDboSchematic $v];set pi [$s NewPagesIter $st];cmcp::check $st
            try {
                for {set page [$pi NextPage $st]} {$page ne "NULL"} {set page [$pi NextPage $st]} {
                    cmcp::check $st;if {[incr count]>10000} {error page_limit};lappend pages [list $s $page]
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set phase checking_complete_group;set seen {}
    foreach pair $pages {
        lassign $pair s page;set st [DboState];set it [$page NewPartInstsIter $st];cmcp::check $st
        try {
            for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
                cmcp::check $st;if {[incr count]>100000} {error object_limit}
                if {[$part GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE} {continue}
                set placed [DboPartInstToDboPlacedInst $part];set pkg [$placed GetPackage $st];cmcp::check $st
                if {$pkg ne $cached} {continue}
                set id [$part GetId $st];cmcp::check $st
                if {![dict exists $mappings $id] || $id in $seen} {error affected_group_mismatch}
                lappend seen $id;set row [dict get $mappings $id]
                foreach {method key} {GetReference reference GetSourcePartName oldSourcePart GetDeviceDesignator deviceDesignator} {
                    set value [cmcp::cs ""];cmcp::check [$placed $method $value]
                    if {[cmcp::str $value] ne [dict get $row $key]} {error old_instance_identity_mismatch}
                }
            }
        } finally {delete_DboPagePartInstsIter $it}
    }
    if {[llength $seen]!=[dict size $mappings]} {error affected_group_incomplete}
    set phase replace_cache
    cmcp::check [$d ReplaceCache [cmcp::cs [dict get $spec oldName]] [cmcp::cs [dict get $spec oldLib]] [cmcp::cs [dict get $spec newName]] [cmcp::cs [dict get $spec newLib]] 1 1]
    set phase restore_instances;set seen {}
    foreach pair $pages {
        lassign $pair s page;set st [DboState];set it [$page NewPartInstsIter $st];cmcp::check $st
        try {
            for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
                cmcp::check $st;set id [$part GetId $st];cmcp::check $st
                if {![dict exists $mappings $id]} {continue}
                if {$id in $seen} {error duplicate_restore_identity};lappend seen $id;set row [dict get $mappings $id]
                cmcp::check [$part SetReference [cmcp::cs [dict get $row reference]]]
                dict for {key value} [dict get $row preserveProperties] {
                    if {$key ni {Value {PCB Footprint}}} {error unsupported_critical_property}
                    cmcp::check [$part SetEffectivePropStringValue [cmcp::cs $key] [cmcp::cs $value]]
                }
                cmcp::restoreUsers $part [dict get $row userProperties]
            }
        } finally {delete_DboPagePartInstsIter $it}
    }
    if {[llength $seen]!=[dict size $mappings]} {error restore_instance_missing}
    set phase save
    foreach pair $pages {lassign $pair s page;cmcp::check [$page MarkModified];cmcp::check [$s MarkModified $page];cmcp::check [$s SavePage $page]}
    set done {};foreach pair $pages {set s [lindex $pair 0];if {$s ni $done} {cmcp::check [$d SaveSchematic $s];lappend done $s}}
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true changed [dict size $mappings]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: cache replacement failed at $phase";exit 1}
