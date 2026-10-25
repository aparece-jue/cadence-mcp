# Fresh read-only source/cache pin+line view comparison, qualified page and reference.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_part_signature.tcl]
if {$argc!=10} {exit 2}
lassign $argv root design library output schematicName pageName reference packageName designator partName
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
    set package [$lib GetPackage [cmcp::cs $packageName] $state];cmcp::check $state
    set device [$package GetDevice [cmcp::cs $designator] $state];cmcp::check $state
    set cell [$device GetCell $state];cmcp::check $state
    set it [$cell NewPartsIter $state];cmcp::check $state;set count 0;set found 0
    try {
        for {set part [$it NextPart $state]} {$part ne "NULL"} {set part [$it NextPart $state]} {
            cmcp::check $state;if {[incr count]>10000} {error part_limit}
            set name [cmcp::cs ""];cmcp::check [$part GetName $name]
            if {[cmcp::str $name] eq $partName} {incr found;set sourcePart $part}
        }
    } finally {delete_DboCellPartsIter $it}
    if {$found!=1} {error ambiguous_source_part}
    set signature [cmcp::partShapeSignature $sourcePart]
    set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    set schematic [$d GetSchematic [cmcp::cs $schematicName] $state];cmcp::check $state
    set page [$schematic GetPage [cmcp::cs $pageName] $state];cmcp::check $state
    set it [$page NewPartInstsIter $state];cmcp::check $state;set count 0;set found 0
    try {
        for {set instance [$it NextPartInst $state]} {$instance ne "NULL"} {set instance [$it NextPartInst $state]} {
            cmcp::check $state;if {[incr count]>100000} {error instance_limit}
            set name [cmcp::cs ""];cmcp::check [$instance GetReference $name]
            if {[cmcp::str $name] eq $reference} {
                set placed [DboPartInstToDboPlacedInst $instance]
                if {$placed eq "NULL"} {error not_placed_instance}
                set unit [cmcp::cs ""];cmcp::check [$placed GetDeviceDesignator $unit]
                if {[cmcp::str $unit] eq $designator} {incr found;set selected $instance}
            }
        }
    } finally {delete_DboPagePartInstsIter $it}
    if {$found!=1} {error ambiguous_instance}
    set state [DboState];set placed [DboPartInstToDboPlacedInst $selected]
    if {$placed eq "NULL"} {error not_placed_instance}
    set part [$placed GetPart $state];cmcp::check $state
    set matches [expr {[cmcp::partShapeSignature $part] eq $signature}]
    set shape [lindex $signature 1]
    if {[lindex $shape 0] eq "ordered_vectors"} {
        set vectors [lindex $shape 1];set vectorCount [llength $vectors];set lineCount 0
        foreach v $vectors {if {[lindex $v 0] eq "line"} {incr lineCount}}
    } else {set lineCount [llength $shape];set vectorCount $lineCount}
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj matches [expr {$matches?"true":"false"}] pinCount [llength [lindex $signature 0]] lineCount $lineCount vectorCount $vectorCount]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: placed view comparison failed: $message";exit 1}
