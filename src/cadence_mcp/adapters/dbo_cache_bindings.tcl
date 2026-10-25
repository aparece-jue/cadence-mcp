# Original bounded read-only helpers; all pointers stay inside the native worker.
proc cmcp::cacheBindingRows {design nativeToCacheId} {
    set state [DboState];set result {};set si 0
    set vi [$design NewViewsIter $state $::IterDefs_SCHEMATICS];cmcp::check $state
    try {
        for {set view [$vi NextView $state]} {$view ne "NULL"} {set view [$vi NextView $state]} {
            cmcp::check $state;cmcp::tick
            set schematic [DboViewToDboSchematic $view];set sid "schematic-[incr si]"
            set schematicName [cmcp::cs ""];cmcp::check [$schematic GetName $schematicName]
            set pi [$schematic NewPagesIter $state];cmcp::check $state;set pageIndex 0
            try {
                for {set page [$pi NextPage $state]} {$page ne "NULL"} {set page [$pi NextPage $state]} {
                    cmcp::check $state;cmcp::tick;set pageId "$sid/page-[incr pageIndex]"
                    set pageName [cmcp::cs ""];cmcp::check [$page GetName $pageName]
                    set instances [$page NewPartInstsIter $state];cmcp::check $state;set partIndex 0
                    try {
                        for {set instance [$instances NextPartInst $state]} {$instance ne "NULL"} {set instance [$instances NextPartInst $state]} {
                            cmcp::check $state;cmcp::tick;set partId "$pageId/part-[incr partIndex]"
                            if {[$instance GetObjectType]!=$::DboBaseObject_PLACED_INSTANCE} {continue}
                            set placed [DboPartInstToDboPlacedInst $instance]
                            if {$placed eq "NULL"} {error missing_placed_cast}
                            set actual [$placed GetPackage $state];cmcp::check $state
                            if {$actual eq "NULL" || ![dict exists $nativeToCacheId $actual]} {error cache_package_not_enumerated}
                            set nativeId [$instance GetId $state];cmcp::check $state
                            set reference [cmcp::cs ""];cmcp::check [$placed GetReference $reference]
                            foreach {method variable} {GetSourceLibName sourceLibrary GetSourcePackageName sourcePackage GetSourcePartName sourcePart GetDeviceDesignator deviceDesignator} {
                                set $variable [cmcp::cs ""];cmcp::check [$placed $method [set $variable]]
                            }
                            set cached [$design GetCachedPackage $sourceLibrary $sourcePackage]
                            set lookupMatches [expr {$cached ne "NULL" && $cached eq $actual}]
                            set sourceName [cmcp::cs ""];set originVerified 0
                            if {$lookupMatches} {
                                set lookupState [$design GetSourceLibName $sourcePackage $cached $sourceName]
                                cmcp::check $lookupState
                                set direct [cmcp::cs ""];cmcp::check [$cached GetSourceLibName $direct]
                                set originVerified [expr {[string equal -nocase [cmcp::str $sourceName] [cmcp::str $sourceLibrary]] && [string equal -nocase [cmcp::str $direct] [cmcp::str $sourceLibrary]]}]
                            }
                            lappend result [cmcp::obj partId [cmcp::q $partId] nativeId $nativeId schematicName [cmcp::q [cmcp::str $schematicName]] pageName [cmcp::q [cmcp::str $pageName]] reference [cmcp::q [cmcp::str $reference]] cachePackageId [cmcp::q [dict get $nativeToCacheId $actual]] sourceLibrary [cmcp::q [cmcp::str $sourceLibrary]] sourcePackage [cmcp::q [cmcp::str $sourcePackage]] sourcePart [cmcp::q [cmcp::str $sourcePart]] deviceDesignator [cmcp::q [cmcp::str $deviceDesignator]] isCached [expr {[$actual IsCachedCopy]?"true":"false"}] lookupMatchesPlaced [expr {$lookupMatches?"true":"false"}] originVerified [expr {$originVerified?"true":"false"}]]
                        }
                    } finally {delete_DboPagePartInstsIter $instances}
                    if {[$state Failed] && [$state Code]!=1022} {error unexpected_instance_iterator_end}
                }
            } finally {delete_DboSchematicPagesIter $pi}
            if {[$state Failed] && [$state Code]!=1022} {error unexpected_page_iterator_end}
        }
    } finally {delete_DboLibViewsIter $vi}
    if {[$state Failed] && [$state Code]!=1022} {error unexpected_schematic_iterator_end}
    return $result
}
