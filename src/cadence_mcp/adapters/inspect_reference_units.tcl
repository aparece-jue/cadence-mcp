# Fixed read-only placement/package/device identities for reference operations.
source [file join [file dirname [info script]] json.tcl]
if {$argc ni {3 4}} {exit 2}
lassign $argv root design output detail
if {$argc == 4 && $detail ne "contents"} {exit 2}
set includeContents [expr {$detail eq "contents"}]
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error dbo_error}}
set session ""; set phase opening
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error no_design}
    set rows {};set count 0;set si 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            cmcp::check $state;set s [DboViewToDboSchematic $v];set sid "schematic-[incr si]"
            set sn [cmcp::cs ""]; $s GetName $sn
            set pi [$s NewPagesIter $state];cmcp::check $state;set pn 0
            try {
                for {set p [$pi NextPage $state]} {$p ne "NULL"} {set p [$pi NextPage $state]} {
                    cmcp::check $state;set pid "$sid/page-[incr pn]";set page [cmcp::cs ""]; $p GetName $page
                    set it [$p NewPartInstsIter $state];cmcp::check $state;set oi 0
                    try {
                        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
                            cmcp::check $state
                            if {[incr count]>100000} {error object_limit}
                            set phase unit_identity
                            set oid "$pid/part-[incr oi]";set ref [cmcp::cs ""];set phase get_reference;cmcp::check [$part GetReference $ref]
                            set phase get_native_id
                            set native [$part GetId $state];cmcp::check $state
                            set phase cast_placed_instance
                            set placed "NULL"
                            if {[$part GetObjectType]==$::DboBaseObject_PLACED_INSTANCE} {set placed [DboPartInstToDboPlacedInst $part]}
                            set kind drawn;set packageId -1;set packageName "";set designator "";set sourceLib "";set sourcePart "";set refDes "";set size 0
                            if {$placed ne "NULL"} {
                                set kind placed
                                set phase placed_get_package
                                set pkg [$placed GetPackage $state];cmcp::check $state
                                if {$pkg eq "NULL"} {error missing_package}
                                set phase package_name
                                # No package numeric identity is assumed.
                                set n [cmcp::cs ""]; cmcp::check [$pkg GetName $n];set packageName [cmcp::str $n]
                                set phase package_get_size
                                set size [$pkg GetSize $state];cmcp::check $state
                                foreach {method key} {GetDeviceDesignator designator GetSourceLibName sourceLib GetSourcePartName sourcePart GetReferenceDesignator refDes} {
                                    set phase "identity_$method"
                                    set n [cmcp::cs ""];cmcp::check [$placed $method $n];set $key [cmcp::str $n]
                                }
                            }
                            set contents {}
                            if {$includeContents} {
                                set phase contents
                                set viewType [$part GetContentsViewType $state]; cmcp::check $state
                                set view [cmcp::cs ""]; cmcp::check [$part GetContentsViewName $view]
                                set lib [cmcp::cs ""]; cmcp::check [$part GetContentsLibName $lib]
                                set primitive [$part GetIsPrimitive $state]; cmcp::check $state
                                set contents [list contents [cmcp::obj viewType $viewType viewName [cmcp::q [cmcp::str $view]] libraryName [cmcp::q [cmcp::str $lib]] primitive $primitive]]
                            }
                            lappend rows [cmcp::obj partId [cmcp::q $oid] nativeId $native schematicName [cmcp::q [cmcp::str $sn]] pageName [cmcp::q [cmcp::str $page]] reference [cmcp::q [cmcp::str $ref]] kind [cmcp::q $kind] isExternalDesignPart [expr {[$part IsExternalDesignPart] ? "true" : "false"}] packageName [cmcp::q $packageName] packageSize $size deviceDesignator [cmcp::q $designator] referenceDesignator [cmcp::q $refDes] sourceLib [cmcp::q $sourceLib] sourcePart [cmcp::q $sourcePart] {*}$contents]
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                    if {$includeContents && [$state Failed] && [$state Code] != 1022} {error unexpected_part_iterator_end}
                }
                if {$includeContents && [$state Failed] && [$state Code] != 1022} {error unexpected_page_iterator_end}
            } finally {delete_DboSchematicPagesIter $pi}
        }
        if {$includeContents && [$state Failed] && [$state Code] != 1022} {error unexpected_view_iterator_end}
    } finally {delete_DboLibViewsIter $vi}
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {
    catch {set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj error [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]];close $f}
    exit 1
}
