# Fixed single-unit definition reference mapping on a new DSN copy.
package require json
source [file join [file dirname [info script]] json.tcl]
if {$argc!=4} {exit 2}
lassign $argv root design specPath output
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
set session "";set phase spec
set rc [catch {
    if {[file size $specPath]>65536} {error spec_limit}
    set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
    set changes [dict get $spec changes]
    if {[llength $changes]<1 || [llength $changes]>64} {error mapping_limit}
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set st [DboState]
    set phase open;set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
    if {$d eq "NULL"} {error no_design}
    set found {};set pages {};set schematics {};set count 0
    set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];cmcp::check $st
    try {
        for {set v [$vi NextView $st]} {$v ne "NULL"} {set v [$vi NextView $st]} {
            cmcp::check $st;set s [DboViewToDboSchematic $v];set sn [cmcp::cs ""];cmcp::check [$s GetName $sn]
            set pi [$s NewPagesIter $st];cmcp::check $st
            try {
                for {set p [$pi NextPage $st]} {$p ne "NULL"} {set p [$pi NextPage $st]} {
                    cmcp::check $st;set pn [cmcp::cs ""];cmcp::check [$p GetName $pn]
                    set it [$p NewPartInstsIter $st];cmcp::check $st
                    try {
                        for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
                            cmcp::check $st
                            if {[incr count]>100000} {error object_limit}
                            set ref [cmcp::cs ""];cmcp::check [$part GetReference $ref]
                            foreach change $changes {
                                if {[cmcp::str $sn] ne [dict get $change schematicName] || [cmcp::str $pn] ne [dict get $change pageName] || [cmcp::str $ref] ne [dict get $change oldReference]} {continue}
                                set key [dict get $change partId]
                                if {[dict exists $found $key]} {error ambiguous_target}
                                set phase identity
                                if {[$part GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE} {error not_placed_instance}
                                set native [$part GetId $st];cmcp::check $st
                                if {$native!=[dict get $change nativeId]} {error native_identity_changed}
                                if {[$part IsExternalDesignPart]} {error external_design_part}
                                set placed [DboPartInstToDboPlacedInst $part]
                                set pkg [$placed GetPackage $st];cmcp::check $st
                                if {$pkg eq "NULL"} {error no_package}
                                set size [$pkg GetSize $st];cmcp::check $st
                                if {$size!=1} {error multiunit_requires_package_mapping}
                                set name [cmcp::cs ""];cmcp::check [$pkg GetName $name]
                                if {[cmcp::str $name] ne [dict get $change packageName]} {error package_changed}
                                dict set found $key $part;dict set pages $p $s;dict set schematics $s 1
                            }
                        }
                    } finally {delete_DboPagePartInstsIter $it}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[dict size $found]!=[llength $changes]} {error missing_target}
    # Every iterator is released before any reference mutation.
    set phase temporary_references
    foreach change $changes {set part [dict get $found [dict get $change partId]];cmcp::check [$part SetReference [cmcp::cs [dict get $change temporaryReference]]]}
    set phase final_references
    foreach change $changes {set part [dict get $found [dict get $change partId]];cmcp::check [$part SetReference [cmcp::cs [dict get $change newReference]]]}
    set phase save
    dict for {p s} $pages {cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p];cmcp::check [$s SavePage $p]}
    dict for {s unused} $schematics {cmcp::check [$d SaveSchematic $s]}
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set receipt [cmcp::obj saved true operation [cmcp::q reference_mapping] changed [llength $changes]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set receipt [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $receipt} finally {close $f}
if {$rc} {exit 1}
