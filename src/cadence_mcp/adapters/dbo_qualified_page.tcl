# Bounded qualified-page lookup via documented native iterators.
proc cmcp::qualifiedPage {d schematicName pageName} {
    set state [DboState]
    set matches {};set count 0
    set vi [$d NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set view [$vi NextView $state]} {$view ne "NULL"} {set view [$vi NextView $state]} {
            cmcp::check $state
            if {[incr count]>100000} {error object_limit}
            set schematic [DboViewToDboSchematic $view];set sn [cmcp::cs ""];cmcp::check [$schematic GetName $sn]
            if {[cmcp::str $sn] ne $schematicName} {continue}
            set pi [$schematic NewPagesIter $state];cmcp::check $state
            try {
                for {set page [$pi NextPage $state]} {$page ne "NULL"} {set page [$pi NextPage $state]} {
                    cmcp::check $state
                    if {[incr count]>100000} {error object_limit}
                    set pn [cmcp::cs ""];cmcp::check [$page GetName $pn]
                    if {[cmcp::str $pn] eq $pageName} {lappend matches [list $schematic $page]}
                }
            } finally {delete_DboSchematicPagesIter $pi}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[llength $matches]!=1} {error ambiguous_page}
    return [lindex $matches 0]
}
