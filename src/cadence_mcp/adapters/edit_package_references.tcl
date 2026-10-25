# Fixed whole-package definition reference map; pointers never leave this worker.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv install design request output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase request
set rc [catch {
    if {[file size $request]>131072} {error request_limit}
    set f [open $request];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 131073]]} finally {close $f}
    set changes [dict get $spec changes];set byNative {};set groups {}
    if {[llength $changes]<1 || [llength $changes]>64} {error mapping_limit}
    foreach c $changes {
        set id [dict get $c nativeId]
        if {![string is integer -strict $id] || [dict exists $byNative $id]} {error duplicate_native_id}
        dict set byNative $id $c
        set key [list [dict get $c schematicName] [dict get $c oldReference]]
        dict lappend groups $key $id
    }
    load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set st [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
    if {$d eq "NULL"} {error missing_design}
    set phase checking_groups;set found {};set pages {};set schematics {};set count 0
    set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st
    try {
        for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
            cmcp::check $st;set s [DboViewToDboSchematic $view];set sn [cmcp::cs ""];cmcp::check [$s GetName $sn]
            set pi [$s NewPagesIter $st];cmcp::check $st
            try {
                for {set page [$pi NextPage $st]} {$page ne "NULL"} {set page [$pi NextPage $st]} {
                    cmcp::check $st;set pn [cmcp::cs ""];cmcp::check [$page GetName $pn]
                    set it [$page NewPartInstsIter $st];cmcp::check $st
                    try {
                        for {set instance [$it NextPartInst $st]} {$instance ne "NULL"} {set instance [$it NextPartInst $st]} {
                            cmcp::check $st;if {[incr count]>100000} {error object_limit}
                            set id [$instance GetId $st];cmcp::check $st;set ref [cmcp::cs ""];cmcp::check [$instance GetReference $ref]
                            set key [list [cmcp::str $sn] [cmcp::str $ref]]
                            if {[dict exists $groups $key] && $id ni [dict get $groups $key]} {error package_group_incomplete}
                            if {![dict exists $byNative $id]} {continue}
                            if {[dict exists $found $id]} {error duplicate_native_identity}
                            set c [dict get $byNative $id]
                            if {[cmcp::str $sn] ne [dict get $c schematicName] || [cmcp::str $pn] ne [dict get $c pageName] || [cmcp::str $ref] ne [dict get $c oldReference]} {error old_scope_mismatch}
                            if {[$instance GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE || [$instance IsExternalDesignPart]} {error unsupported_instance}
                            set placed [DboPartInstToDboPlacedInst $instance];set pkg [$placed GetPackage $st];cmcp::check $st
                            if {$pkg eq "NULL"} {error missing_package}
                            set size [$pkg GetSize $st];cmcp::check $st
                            if {$size!=[dict get $c packageSize]} {error package_size_changed}
                            set n [cmcp::cs ""];cmcp::check [$pkg GetName $n]
                            if {[cmcp::str $n] ne [dict get $c packageName]} {error package_name_changed}
                            set cached [$d GetCachedPackage [cmcp::cs [dict get $c sourceLib]] [cmcp::cs [dict get $c packageName]]]
                            if {$cached eq "NULL" || $cached ne $pkg} {error cache_source_identity_changed}
                            foreach {method field} {GetReferenceDesignator oldFullReference GetDeviceDesignator deviceDesignator GetSourcePartName sourcePart GetSourceLibName sourceLib} {
                                set value [cmcp::cs ""];cmcp::check [$placed $method $value]
                                if {[cmcp::str $value] ne [dict get $c $field]} {error old_unit_identity_changed}
                            }
                            dict set found $id $instance;dict set pages $page $s;dict set schematics $s 1
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[dict size $found]!=[llength $changes]} {error missing_mapped_unit}
    # All affected units share the group's temporary base; cycles never use final names early.
    set phase temporary_references
    foreach c $changes {set part [dict get $found [dict get $c nativeId]];cmcp::check [$part SetReference [cmcp::cs [dict get $c temporaryReference]]]}
    set phase final_references
    foreach c $changes {set part [dict get $found [dict get $c nativeId]];cmcp::check [$part SetReference [cmcp::cs [dict get $c newReference]]]}
    set phase save
    dict for {page s} $pages {cmcp::check [$page MarkModified];cmcp::check [$s MarkModified $page];cmcp::check [$s SavePage $page]}
    dict for {s unused} $schematics {cmcp::check [$d SaveSchematic $s]}
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q package_reference_mapping] changed [llength $changes]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
