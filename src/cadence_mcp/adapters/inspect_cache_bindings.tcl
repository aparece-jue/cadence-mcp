# Read DSN cache via its design object; external OLB is not the target.
# argv: installRoot copiedOLB outputJSON maxObjects
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_cache_bindings.tcl]
namespace eval cmcp {variable count 0; variable limit 100000}
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_error_code_[$s Code]"}}
proc cmcp::tick {} {variable count; variable limit; if {[incr count] > $limit} {error "object_limit"}}
proc cmcp::point {p} {return [cmcp::arr [list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]]]}
if {$argc != 4} {exit 2}
lassign $argv root source output cmcp::limit
set session ""
set rc [catch {
    load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
    set session [DboTclHelper_sCreateSession]
    set state [DboState]
    set lib [$session GetDesignAndSchematics [cmcp::cs $source] $state]; cmcp::check $state
    if {$lib eq "NULL"} {error "no_library"}
    set packages {}; set devices {}; set cells {}; set parts {}; set pins {};set origins {};set nativeToCacheId {}
    # Official capDB/capExportDesignCache.tcl uses NewCachesIter and the
    # BaseObject -> LibObject -> Package casts for cached package objects (31).
    # NewPackagesIter alone lists local definitions and misses these entries.
    set packageObjects {};set packageSeen {}
    set cacheIter [$lib NewCachesIter $state];cmcp::check $state
    try {
        for {set obj [$cacheIter NextCachedObject $state]} {$obj ne "NULL"} {set obj [$cacheIter NextCachedObject $state]} {
            cmcp::check $state;cmcp::tick
            if {[$obj GetObjectType]!=31} {continue}
            set pkg [DboLibObjectToDboPackage [DboBaseObjectToDboLibObject $obj]]
            if {$pkg eq "NULL"} {error missing_cached_package}
            if {$pkg ni $packageSeen} {lappend packageObjects $pkg;lappend packageSeen $pkg}
        }
    } finally {delete_DboDesignCachesIter $cacheIter}
    set localIter [$lib NewPackagesIter $state];cmcp::check $state
    try {
        for {set pkg [$localIter NextPackage $state]} {$pkg ne "NULL"} {set pkg [$localIter NextPackage $state]} {
            cmcp::check $state;cmcp::tick
            if {$pkg ni $packageSeen} {lappend packageObjects $pkg;lappend packageSeen $pkg}
        }
    } finally {delete_DboLibPackagesIter $localIter}
    # Enumeration EOF state belongs to the completed iterator, not package reads.
    set state [DboState]
    try {
        set packageIndex 0
        foreach pkg $packageObjects {
            set state [DboState]; cmcp::tick
            set packageId "package-[incr packageIndex]"
            dict set nativeToCacheId $pkg $packageId
            set isCached [$pkg IsCachedCopy];set sourceLibrary [cmcp::cs ""]
            set originState [$pkg GetSourceLibName $sourceLibrary];set verifiedOrigin 0
            if {$isCached} {cmcp::check $originState;set verifiedOrigin [expr {[cmcp::str $sourceLibrary] ne ""}]}
            if {[$originState Failed]} {set sourceLibrary [cmcp::cs ""]}
            lappend origins [cmcp::obj cachePackageId [cmcp::q $packageId] isCached [expr {$isCached?"true":"false"}] sourceLibrary [cmcp::q [cmcp::str $sourceLibrary]] originVerified [expr {$verifiedOrigin?"true":"false"}]]
            set name [cmcp::cs ""]; cmcp::check [$pkg GetName $name]
            set size [$pkg GetSize $state]; cmcp::check $state
            set homogeneous [$pkg IsHomogeneous $state]; cmcp::check $state
            set footprint [cmcp::cs ""]; cmcp::check [$pkg GetPCBFootprint $footprint]
            lappend packages [cmcp::obj objectId [cmcp::q $packageId] name [cmcp::q [cmcp::str $name]] size $size homogeneous [expr {$homogeneous ? "true" : "false"}] footprint [cmcp::q [cmcp::str $footprint]]]
            set di [$pkg NewDevicesIter $state]; cmcp::check $state
            try {
                set deviceIndex 0
                for {set device [$di NextDevice $state]} {$device ne "NULL"} {set device [$di NextDevice $state]} {
                    cmcp::check $state; cmcp::tick
                    set deviceId "$packageId/device-[incr deviceIndex]"
                    set designator [cmcp::cs ""]; cmcp::check [$device GetDesignator $designator]
                    set position [$device GetPosition $state]; cmcp::check $state
                    set cell [$device GetCell $state]; cmcp::check $state
                    if {$cell eq "NULL"} {error "missing_cell"}
                    set cellId "$deviceId/cell"
                    set cellName [cmcp::cs ""]; cmcp::check [$device GetCellName $cellName]
                    cmcp::tick
                    lappend devices [cmcp::obj objectId [cmcp::q $deviceId] packageId [cmcp::q $packageId] designator [cmcp::q [cmcp::str $designator]] position $position cellId [cmcp::q $cellId]]
                    lappend cells [cmcp::obj objectId [cmcp::q $cellId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $cellName]]]
                    set pi [$cell NewPartsIter $state]; cmcp::check $state
                    try {
                        set partIndex 0
                        for {set part [$pi NextPart $state]} {$part ne "NULL"} {set part [$pi NextPart $state]} {
                            cmcp::check $state; cmcp::tick
                            set partId "$cellId/part-[incr partIndex]"
                            set partName [cmcp::cs ""]; cmcp::check [$part GetName $partName]
                            lappend parts [cmcp::obj objectId [cmcp::q $partId] cellId [cmcp::q $cellId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $partName]]]
                            set pinsIter [$part NewLPinsIter $state]; cmcp::check $state
                            try {
                                set pinIndex 0
                                for {set pin [$pinsIter NextPin $state]} {$pin ne "NULL"} {set pin [$pinsIter NextPin $state]} {
                                    cmcp::check $state; cmcp::tick
                                    set pinId "$partId/pin-[incr pinIndex]"
                                    set pinName [cmcp::cs ""]; cmcp::check [$pin GetPinName $pinName]
                                    set logicalPosition [$pin GetPinPosition $state]; cmcp::check $state
                                    set number [cmcp::cs ""]; cmcp::check [$device GetPinNumber $logicalPosition $number]
                                    set pinType [$pin GetPinType $state]; cmcp::check $state
                                    set visible [$pin GetIsVisible $state]; cmcp::check $state
                                    set shared [$device GetIsShared $logicalPosition $state]; cmcp::check $state
                                    set swapId [$device GetPinSwapId $logicalPosition $state]; cmcp::check $state
                                    set hotSpot [$pin GetHotSpot $state]; cmcp::check $state
                                    lappend pins [cmcp::obj objectId [cmcp::q $pinId] partId [cmcp::q $partId] deviceId [cmcp::q $deviceId] packageId [cmcp::q $packageId] name [cmcp::q [cmcp::str $pinName]] position $logicalPosition number [cmcp::q [cmcp::str $number]] pinType $pinType visible [expr {$visible ? "true" : "false"}] shared [expr {$shared ? "true" : "false"}] swapId $swapId hotSpot [cmcp::point $hotSpot]]
                                }
                            } finally {delete_DboLibPartPinsIter $pinsIter}
                        }
                    } finally {delete_DboCellPartsIter $pi}
                }
            } finally {delete_DboPackageDevicesIter $di}
        }
    } finally {set packageObjects {};set packageSeen {}}
    set stream [open $output {WRONLY CREAT EXCL}]
    try {
        fconfigure $stream -encoding utf-8 -translation lf
        set bindings [cmcp::cacheBindingRows $lib $nativeToCacheId]
        set definitions [cmcp::obj package [cmcp::arr $packages] device [cmcp::arr $devices] cell [cmcp::arr $cells] part [cmcp::arr $parts] pin [cmcp::arr $pins]]
        puts -nonewline $stream [cmcp::obj definitions $definitions origins [cmcp::arr $origins] bindings [cmcp::arr $bindings]]
    } finally {close $stream}
} message options]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: library inspection failed: $message [string range [dict get $options -errorinfo] 0 2047]"; exit 1}
