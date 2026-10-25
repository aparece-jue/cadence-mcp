# Independent root/view/page/count inventory. rawRefCount is not a dependency proof.
source [file join [file dirname [info script]] json.tcl]
if {$argc!=3} {exit 2}
lassign $argv root design output
proc cmcp::cs {s} {return [DboTclHelper_sMakeCString $s]}
proc cmcp::str {s} {return [DboTclHelper_sGetConstCharPtr $s]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_status_[$s Code]"}}
proc cmcp::count_iter {page make next remove} {
    set state [DboState];set it [$page $make $state];cmcp::check $state
    if {$it eq "NULL"} {error missing_iterator}
    set n 0
    try {
        for {set o [$it $next $state]} {$o ne "NULL"} {set o [$it $next $state]} {
            cmcp::check $state
            if {[incr n]>100000} {error object_limit}
        }
    } finally {$remove $it}
    return $n
}
set session "";set phase open
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession];set state [DboState]
    set d [$session GetDesignAndSchematics [cmcp::cs $design] $state];cmcp::check $state
    if {$d eq "NULL"} {error no_design}
    set ro [$d GetRootSchematic $state];cmcp::check $state
    if {$ro eq "NULL"} {error missing_root}
    set rootName [cmcp::cs ""];cmcp::check [$ro GetName $rootName]
    set schematics {};set pages {};set n 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set v [$vi NextView $state]} {$v ne "NULL"} {set v [$vi NextView $state]} {
            cmcp::check $state
            if {[incr n]>10000} {error view_limit}
            set s [DboViewToDboSchematic $v];set sn [cmcp::cs ""];cmcp::check [$s GetName $sn]
            lappend schematics [cmcp::obj name [cmcp::q [cmcp::str $sn]] rawRefCount [$s GetRefCount]]
            set ps [DboState];set pi [$s NewPagesIter $ps];cmcp::check $ps
            try {
                for {set p [$pi NextPage $ps]} {$p ne "NULL"} {set p [$pi NextPage $ps]} {
                    cmcp::check $ps
                    if {[llength $pages]>=10000} {error page_limit}
                    set pn [cmcp::cs ""];cmcp::check [$p GetName $pn];set counts {}
                    foreach {key method} {part GetPartInstCount wire GetWireCount busEntry GetBusEntryCount port GetPortCount global GetGlobalCount offpage GetOffPageConnectorCount graphic GetCommentGraphicCount} {
                        set stateCount [DboState];set count [$p $method $stateCount];cmcp::check $stateCount
                        if {$count<0 || $count>100000} {error count_limit}
                        lappend counts $key $count
                    }
                    foreach {key make next remove} {
                        titleblock NewTitleBlocksIter NextTitleBlock delete_DboPageTitleBlocksIter
                        erc NewERCsIter NextERC delete_DboPageERCsIter
                        bookmark NewBookMarksIter NextBookMark delete_DboPageBookMarksIter
                    } {lappend counts $key [cmcp::count_iter $p $make $next $remove]}
                    lappend pages [cmcp::obj schematicName [cmcp::q [cmcp::str $sn]] name [cmcp::q [cmcp::str $pn]] counts [cmcp::obj {*}$counts]]
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    set f [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj rootName [cmcp::q [cmcp::str $rootName]] schematics [cmcp::arr $schematics] pages [cmcp::arr $pages]]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: document meta $phase $message";exit 1}
