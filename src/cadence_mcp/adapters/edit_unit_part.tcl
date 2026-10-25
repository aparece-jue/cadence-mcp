# Fixed unit-aware pose/delete, bound native ID plus full package/device identity.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
package require json
if {$argc!=4} {exit 2}
lassign $argv root design request output
if {[file size $request]>200000} {exit 2}
set f [open $request];fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 200001]];close $f
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
set session "";set phase load
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    set phase page_lookup;lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] schematic page
    set state [DboState];set unit [dict get $spec unit];set target "NULL";set matches 0;set count 0
    set it [$page NewPartInstsIter $state];cmcp::check $state
    try {
        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
            cmcp::check $state;if {[incr count]>100000} {error instance_limit}
            set id [$part GetId $state];cmcp::check $state
            if {$id==[dict get $unit nativeId]} {set target $part;incr matches}
        }
    } finally {delete_DboPagePartInstsIter $it}
    if {$matches!=1} {error ambiguous_target_id}
    set state [DboState];set phase unit_identity
    set placed [DboPartInstToDboPlacedInst $target]
    if {$placed eq "NULL"} {error target_not_placed}
    foreach {method key} {GetReference reference GetReferenceDesignator referenceDesignator GetDeviceDesignator deviceDesignator} {
        set value [cmcp::cs ""];cmcp::check [$placed $method $value]
        if {[cmcp::str $value] ne [dict get $unit $key]} {error old_unit_identity_mismatch}
    }
    set package [$placed GetPackage $state];cmcp::check $state
    set name [cmcp::cs ""];cmcp::check [$package GetName $name]
    if {[cmcp::str $name] ne [dict get $unit packageName]} {error old_package_mismatch}
    if {[$package GetSize $state]!=[dict get $unit packageSize]} {error old_package_size_mismatch};cmcp::check $state
    set old [dict get $spec oldGeometry]
    set loc [$target GetLocation $state];cmcp::check $state
    set rot [$target GetRotation $state];cmcp::check $state
    set mir [$target GetMirror $state];cmcp::check $state
    if {[list [DboTclHelper_sGetCPointX $loc] [DboTclHelper_sGetCPointY $loc]] ne [dict get $old location] || $rot!=[dict get $old rotationCode] || $mir!=[dict get $old mirrorCode]} {error old_pose_mismatch}
    set operation [dict get $spec operation];set phase $operation
    if {$operation eq "delete"} {
        cmcp::check [$page DeletePartInst $target]
        set target "NULL";set placed "NULL"
    } elseif {$operation eq "set_pose"} {
        set pose [dict get $spec newGeometry]
        cmcp::check [$target SetMirror [dict get $pose mirrorCode]]
        cmcp::check [$target SetRotation [dict get $pose rotationCode]]
        cmcp::check [$target SetLocation [DboTclHelper_sMakeCPoint {*}[dict get $pose location]]]
    } else {error invalid_operation}
    set phase save
    cmcp::check [$page MarkModified];cmcp::check [$schematic MarkModified $page]
    cmcp::check [$schematic SavePage $page];cmcp::check [$d SaveSchematic $schematic]
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set result [cmcp::obj saved true operation [cmcp::q $operation] nativeId [dict get $unit nativeId]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
