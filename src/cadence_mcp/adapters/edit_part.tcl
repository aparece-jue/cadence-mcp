# Fixed part-definition pose/delete operation on a new owned DSN copy.
# argv: install design receipt schematic page reference operation oldX oldY oldR oldM x y r m
source [file join [file dirname [info script]] json.tcl]
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
if {$argc!=15} {exit 2}
lassign $argv root design output sn pn ref op ox oy oldR oldM x y r m
if {$op ni {set_pose delete}} {exit 2}
foreach n [list $ox $oy $oldR $oldM $x $y $r $m] {if {![string is integer -strict $n] || abs($n)>1000000} {exit 2}}
if {$r ni {0 1 2 3} || $m ni {0 1}} {exit 2}
set session "";set phase opening
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error no_design}
    set phase schematic_lookup;set s [$d GetSchematic [cmcp::cs $sn] $state];cmcp::check $state
    if {$s eq "NULL"} {error no_schematic}
    set phase page_lookup;set p "NULL";set pageMatches 0;set pageCount 0
    set pages [$s NewPagesIter $state];cmcp::check $state
    try {
        for {set candidate [$pages NextPage $state]} {$candidate ne "NULL"} {set candidate [$pages NextPage $state]} {
            cmcp::check $state
            if {[incr pageCount]>100000} {error page_limit}
            set pageName [cmcp::cs ""];cmcp::check [$candidate GetName $pageName]
            if {[cmcp::str $pageName] eq $pn} {set p $candidate;incr pageMatches}
        }
    } finally {delete_DboSchematicPagesIter $pages}
    if {$pageMatches!=1} {error ambiguous_or_missing_page}
    set state [DboState]
    if {$p eq "NULL"} {error no_page}
    set phase identity;set target "NULL";set matches 0;set count 0
    set it [$p NewPartInstsIter $state];cmcp::check $state
    try {
        for {set part [$it NextPartInst $state]} {$part ne "NULL"} {set part [$it NextPartInst $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set actual [cmcp::cs ""];cmcp::check [$part GetReference $actual]
            if {[cmcp::str $actual] eq $ref} {set target $part;incr matches}
        }
    } finally {delete_DboPagePartInstsIter $it}
    if {$matches!=1} {error ambiguous_or_missing_target}
    set state [DboState]
    set loc [$target GetLocation $state];cmcp::check $state
    set rot [$target GetRotation $state];cmcp::check $state
    set mir [$target GetMirror $state];cmcp::check $state
    if {[DboTclHelper_sGetCPointX $loc]!=$ox || [DboTclHelper_sGetCPointY $loc]!=$oy || $rot!=$oldR || $mir!=$oldM} {error old_pose_mismatch}
    set phase $op
    if {$op eq "delete"} {
        cmcp::check [$p DeletePartInst $target]
        # The removed native pointer must never be dereferenced again.
        set target "NULL"
    } else {
        cmcp::check [$target SetMirror $m]
        cmcp::check [$target SetRotation $r]
        cmcp::check [$target SetLocation [DboTclHelper_sMakeCPoint $x $y]]
    }
    set phase save
    cmcp::check [$p MarkModified];cmcp::check [$s MarkModified $p]
    cmcp::check [$s SavePage $p];cmcp::check [$d SaveSchematic $s]
    cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
    set receipt [cmcp::obj saved true operation [cmcp::q $op]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set receipt [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}]
try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $receipt} finally {close $f}
if {$rc} {exit 1}
