# Self-authored two-pin library fixture. No installation or existing OLB writes.
# argv: installRoot newOLB
if {$argc != 2} {exit 2}
lassign $argv root target
if {[file exists $target]} {puts stderr "Target already exists"; exit 2}
proc cs {v} {return [DboTclHelper_sMakeCString $v]}
proc check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
source [file join [file dirname [info script]] json.tcl]
set session "";set phase load_dll
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set phase create_session
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set phase create_lib
    set lib [$session CreateLib [cs $target] $state]; check $state
    if {$lib eq "NULL"} {error "no_library"}
    set phase new_package
    set package [$lib NewPackage [cs MCP_R_FIXTURE] $state]; check $state
    set phase set_reference_template
    check [$package SetReferenceTemplate [cs R?]]
    set phase set_footprint
    check [$package SetPCBFootprint [cs MCP_TEST_FOOTPRINT]]
    set phase new_cell
    set cell [$lib NewCell [cs MCP_R_CELL] $state]; check $state
    set phase new_part
    set part [$lib NewPart [cs MCP_R_PART] $state]; check $state
    set phase add_part
    check [$cell AddPart $part]
    set phase new_device
    set device [$package NewDevice [cs A] 0 $cell $state]; check $state
    foreach {number name x y startX startY} {1 A -20 0 -10 0 2 B 20 0 10 0} {
        set posPointer [DboTclHelper_sMakeInt]
        set phase new_pin_number_$number
    check [$device NewPinNumber [cs $number] $posPointer 0 -1]
        set phase get_pin_position_$number
    set position [$device GetPinPosition [cs $number] $state]; check $state
        set phase new_symbol_pin_$number
    set pin [$part NewSymbolPinScalar $state [cs $name] 4 [DboTclHelper_sMakeCPoint $startX $startY] [DboTclHelper_sMakeCPoint $x $y] 1 $position]; check $state
        if {$pin eq "NULL"} {error "no_pin"}
    }
    set phase mark_library
    check [$session MarkAllLibForSave $lib]
    set phase save_library
    check [$session SaveLib $lib]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set out [open [file join [file dirname $target] native-result.json] {WRONLY CREAT EXCL}]
try {fconfigure $out -encoding utf-8 -translation lf;puts $out [cmcp::obj caught $rc phase [cmcp::q $phase] message [cmcp::q [string range $message 0 2047]]]} finally {close $out}
if {$rc} {puts stderr "Fixture creation failed phase=$phase : $message"; exit 1}
puts "CREATED_SINGLE_LIBRARY_FIXTURE"
