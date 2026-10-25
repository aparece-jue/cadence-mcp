# Fixed declaration-to-OLB construction. No eval or arbitrary native method input.
package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_create_vector.tcl]
if {$argc!=4} {exit 2}
lassign $argv root specPath target output
if {[file exists $target]} {exit 2}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
proc cmcp::pt {p} {return [DboTclHelper_sMakeCPoint {*}$p]}
set session "";set phase read_spec;set count 0
set rc [catch {
    if {[file size $specPath]>65536} {error spec_limit}
    set f [open $specPath];try {fconfigure $f -encoding utf-8;set spec [::json::json2dict [read $f 65537]]} finally {close $f}
    set phase load_dll
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set phase create_lib;set lib [$session CreateLib [cmcp::cs $target] $state];cmcp::check $state
    if {$lib eq "NULL"} {error no_library}
    if {[dict exists $spec packages]} {set declarations [dict get $spec packages]} else {set declarations [list $spec]}
    foreach spec $declarations {
    set phase create_package;set pkg [$lib NewPackage [cmcp::cs [dict get $spec packageName]] $state];cmcp::check $state
    cmcp::check [$pkg SetReferenceTemplate [cmcp::cs [dict get $spec referenceTemplate]]]
    cmcp::check [$pkg SetPCBFootprint [cmcp::cs [dict get $spec footprint]]]
    set cells {};set parts {}
    foreach symbol [dict get $spec symbols] {
        if {[incr count]>100000} {error object_limit}
        set phase create_symbol
        if {[dict exists $cells [dict get $symbol cellName]]} {set cell [dict get $cells [dict get $symbol cellName]]} else {set cell [$lib NewCell [cmcp::cs [dict get $symbol cellName]] $state];cmcp::check $state}
        set part [$lib NewPart [cmcp::cs [dict get $symbol partName]] $state];cmcp::check $state
        cmcp::check [$cell AddPart $part]
        dict set cells [dict get $symbol cellName] $cell;dict set parts [dict get $symbol partName] $part
    }
    foreach dev [dict get $spec devices] {
        if {[incr count]>100000} {error object_limit}
        set phase create_device
        set device [$pkg NewDevice [cmcp::cs [dict get $dev designator]] [dict get $dev position] [dict get $cells [dict get $dev cellName]] $state];cmcp::check $state
        foreach mapping [dict get $dev mapping] {
            if {[incr count]>100000} {error object_limit}
            set phase create_physical_mapping
            set position [dict get $mapping position];set pointer [DboTclHelper_sMakeInt $position]
            cmcp::check [$device NewPinNumber [cmcp::cs [dict get $mapping number]] $pointer [expr {[dict get $mapping shared] ? 1 : 0}] [dict get $mapping swapId]]
            set actual [$device GetPinPosition [cmcp::cs [dict get $mapping number]] $state];cmcp::check $state
            if {$actual!=$position} {error physical_logical_position_mismatch}
        }
    }
    foreach symbol [dict get $spec symbols] {
        set part [dict get $parts [dict get $symbol partName]]
        foreach pin [dict get $symbol pins] {
            if {[incr count]>100000} {error object_limit}
            set phase create_logical_pin
            set object [$part NewSymbolPinScalar $state [cmcp::cs [dict get $pin name]] [dict get $pin pinType] [cmcp::pt [dict get $pin start]] [cmcp::pt [dict get $pin hotSpot]] [expr {[dict get $pin visible] ? 1 : 0}] [dict get $pin position]];cmcp::check $state
            if {$object eq "NULL"} {error missing_pin}
        }
        foreach line [dict get $symbol lines] {
            if {[incr count]>100000} {error object_limit}
            set phase create_symbol_line
            set object [$part NewLine $state [cmcp::pt [dict get $line start]] [cmcp::pt [dict get $line end]] [dict get $line style] [dict get $line width]];cmcp::check $state
            if {$object eq "NULL"} {error missing_line}
        }
        if {[dict exists $symbol vectors]} {
            foreach vector [dict get $symbol vectors] {
                if {[incr count]>100000} {error object_limit}
                set phase "create_vector_[dict get $vector kind]"
                cmcp::createDeclaredVector $part $vector
            }
        }
    }
    }
        # Typed vectors follow legacy lines in the declared order.
    set phase mark_library;cmcp::check [$session MarkAllLibForSave $lib]
    set phase save_library;cmcp::check [$session SaveLib $lib]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}]
try {
    fconfigure $f -encoding utf-8 -translation lf
    if {$rc} {puts $f [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} else {puts $f [cmcp::obj saved true operation [cmcp::q create_library]]}
} finally {close $f}
if {$rc} {exit 1}
