# Self-authored two-pin library fixture. No installation or existing OLB writes.
# argv: installRoot newOLB
if {$argc != 2} {exit 2}
lassign $argv root target
if {[file exists $target]} {puts stderr "Target already exists"; exit 2}
proc cs {v} {return [DboTclHelper_sMakeCString $v]}
proc check {s} {if {[$s Failed]} {error "dbo_error"}}
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set lib [$session CreateLib [cs $target] $state]; check $state
    if {$lib eq "NULL"} {error "no_library"}
    set package [$lib NewPackage [cs MCP_R_FIXTURE] $state]; check $state
    check [$package SetReferenceTemplate [cs R?]]
    check [$package SetPCBFootprint [cs MCP_TEST_FOOTPRINT]]
    set cell [$lib NewCell [cs MCP_R_CELL] $state]; check $state
    set part [$lib NewPart [cs MCP_R_PART] $state]; check $state
    check [$cell AddPart $part]
    set device [$package NewDevice [cs A] 0 $cell $state]; check $state
    foreach {number name x y startX startY} {1 A -20 0 -10 0 2 B 20 0 10 0} {
        set posPointer [DboTclHelper_sMakeInt]
        check [$device NewPinNumber [cs $number] $posPointer 0 -1]
        set position [$device GetPinPosition [cs $number] $state]; check $state
        set pin [$part NewSymbolPinScalar $state [cs $name] 4 [DboTclHelper_sMakeCPoint $startX $startY] [DboTclHelper_sMakeCPoint $x $y] 1 $position]; check $state
        if {$pin eq "NULL"} {error "no_pin"}
    }
    check [$session MarkAllLibForSave $lib]
    check [$session SaveLib $lib]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "Fixture creation failed: $message"; exit 1}
puts "CREATED_SINGLE_LIBRARY_FIXTURE"
