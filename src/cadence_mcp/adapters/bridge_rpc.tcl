# Version 2 allowlisted RPC; sessions default to read, fixed metadata writes require opt-in.
namespace eval ::cmcpBridge {
    variable generation
    variable sessions
    variable lost
    variable observation
    variable pollTimer
    variable hooksRegistered
    if {![info exists generation]} {set generation 1}
    if {![info exists sessions]} {set sessions [dict create]}
    if {![info exists lost]} {set lost 0}
    if {![info exists observation]} {set observation ""}
    if {![info exists pollTimer]} {set pollTimer ""}
    if {![info exists hooksRegistered]} {set hooksRegistered 0}
}
proc ::cmcpBridge::invalidate {} {
    variable generation; variable sessions
    incr generation
    set sessions [dict create]
}
proc ::cmcpBridge::dirty {} {
    set design [GetActivePMDesign]
    if {$design eq "NULL" || $design eq ""} {return unknown}
    set state [DboState]
    set value [$design IsModified $state]
    if {[$state Failed]} {return unknown}
    return [expr {$value ? "dirty" : "clean"}]
}
proc ::cmcpBridge::observe {} {
    variable config; variable lost; variable observation
    set path [activeDesign]
    set dirty [dirty]
    set signature [list $path $dirty]
    if {$observation ne "" && $signature ne $observation} {invalidate}
    set observation $signature
    if {![string equal -nocase $path [dict get $config expectedDesign]]} {
        if {!$lost} {invalidate}
        set lost 1
    }
    return [list $path $dirty]
}
proc ::cmcpBridge::watch {} {
    variable listener; variable pollTimer
    if {$listener eq ""} {return}
    if {[catch {observe}]} {invalidate}
    set pollTimer [after 250 ::cmcpBridge::watch]
}
proc ::cmcpBridge::eventEnabled {args} {
    variable listener
    return [expr {$listener ne ""}]
}
proc ::cmcpBridge::onEvent {args} {
    variable listener
    if {$listener ne ""} {invalidate}
}
proc ::cmcpBridge::lifecycleStart {} {
    variable pollTimer; variable lost; variable observation; variable hooksRegistered
    set lost 0; set observation ""
    invalidate
    if {$pollTimer ne ""} {after cancel $pollTimer}
    if {!$hooksRegistered && [llength [info commands RegisterAction]]} {
        foreach tag {_cdnOrOnDesignPostSave _cdnOrNotifyDesignPostSaveAs _cdnOrNotifyDesignPreClose _cdnOrNotifyDesignOpened _cdnOrOnPostDesignConnectivityChange} {
            RegisterAction $tag ::cmcpBridge::eventEnabled "" ::cmcpBridge::onEvent ""
        }
        set hooksRegistered 1
    }
    watch
}
proc ::cmcpBridge::lifecycleStop {} {
    variable pollTimer
    if {$pollTimer ne ""} {after cancel $pollTimer; set pollTimer ""}
    invalidate
}
proc ::cmcpBridge::stateCheck {state} {if {[$state Failed]} {error "dbo_error"}}
proc ::cmcpBridge::nameOf {object} {
    set text [DboTclHelper_sMakeCString]
    stateCheck [$object GetName $text]
    return [DboTclHelper_sGetConstCharPtr $text]
}
proc ::cmcpBridge::pages {} {
    set state [DboState]
    set design [GetActivePMDesign]
    set active "NULL"
    catch {set active [GetActivePage]}
    set result {}; set n 0
    set views [$design NewViewsIter $state $::IterDefs_SCHEMATICS]; stateCheck $state
    try {
        for {set view [$views NextView $state]} {$view ne "NULL"} {set view [$views NextView $state]} {
            stateCheck $state
            set schematic [DboViewToDboSchematic $view]
            set name [nameOf $schematic]
            set iterator [$schematic NewPagesIter $state]; stateCheck $state
            try {
                for {set page [$iterator NextPage $state]} {$page ne "NULL"} {set page [$iterator NextPage $state]} {
                    stateCheck $state
                    if {[incr n] > 500} {error "result_limit"}
                    lappend result [cmcp::obj pageId [cmcp::q "page-$n"] schematicName [cmcp::q $name] name [cmcp::q [nameOf $page]] active [expr {$page eq $active ? "true" : "false"}]]
                }
            } finally {delete_DboSchematicPagesIter $iterator}
        }
    } finally {delete_DboLibViewsIter $views}
    return [cmcp::obj pages [cmcp::arr $result] complete true]
}
proc ::cmcpBridge::selection {snapshotId} {
    set page "NULL"
    catch {set page [GetActivePage]}
    if {$page eq "NULL" || $page eq ""} {error "no_active_page"}
    # Bind selection to a page actually enumerated from the active design.
    set document [::json::json2dict [pages]]
    set found 0
    foreach item [dict get $document pages] {if {[dict get $item active]} {set found 1}}
    if {!$found} {error "target_changed"}
    set result {}; set n 0
    foreach object [GetSelectedObjects] {
        if {[incr n] > 200} {error "result_limit"}
        set type [$object GetObjectType]
        # No native pointer or dereferenceable handle crosses the protocol.
        lappend result [cmcp::obj objectId [cmcp::q "$snapshotId/selection-$n"] objectType $type]
    }
    return [cmcp::obj selectionSnapshotId [cmcp::q $snapshotId] pageName [cmcp::q [nameOf $page]] items [cmcp::arr $result] complete true writable false]
}
proc ::cmcpBridge::drc_configuration {} {
    foreach command {::capGetDRCConfigData ::capIsOnlineDrcEnabled ::COrDRCTclInterface_sIsDRCFlowEnabled} {
        if {![llength [info commands $command]]} {error capability_unavailable}
    }
    set raw [::capGetDRCConfigData]
    if {[string bytelength $raw]>65536} {error result_limit}
    set parsed [::json::json2dict $raw]
    if {![dict exists $parsed DesignPath] || ![string equal -nocase [file normalize [dict get $parsed DesignPath]] [activeDesign]]} {error target_changed}
    # Compact only inspected flags and ERC data before crossing the16KiB transport.
    set fields {};set count 0
    foreach key [lsort [dict keys $parsed]] {
        if {![string match Run* $key]} {continue}
        if {[incr count]>128 || ![regexp {^Run[A-Za-z]+$} $key] || [dict get $parsed $key] ni {0 1}} {error invalid_drc_configuration}
        lappend fields $key [cmcp::q [dict get $parsed $key]]
    }
    set matrix {};set expected {IN_PIN IO_PIN OUT_PIN OC_PIN PAS_PIN HIZ_PIN OE_PIN IN_PORT IO_PORT OUT_PORT OC_PORT PAS_PORT HIZ_PORT OE_PORT DBGLOBAL UNCONNECTED}
    if {![dict exists $parsed ERCMatrix] || [lsort [dict keys [dict get $parsed ERCMatrix]]] ne [lsort $expected]} {error invalid_drc_configuration}
    foreach key $expected {
        set values [dict get $parsed ERCMatrix $key];if {[llength $values]!=16} {error invalid_drc_configuration}
        set cells {};foreach value $values {if {$value ni {- W E}} {error invalid_drc_configuration};lappend cells [cmcp::q $value]}
        lappend matrix $key [cmcp::arr $cells]
    }
    lappend fields ERCMatrix [cmcp::obj {*}$matrix]
    set raw [cmcp::obj {*}$fields]
    set online [::capIsOnlineDrcEnabled];set flow [::COrDRCTclInterface_sIsDRCFlowEnabled]
    if {$online ni {0 1} || $flow ni {0 1}} {error invalid_drc_configuration}
    return [cmcp::obj nativeConfiguration [cmcp::q $raw] onlineEnabled [expr {$online?"true":"false"}] flowEnabled [expr {$flow?"true":"false"}]]
}
proc ::cmcpBridge::drc_counts {} {
    foreach command {::COrDRCTclInterface_GetElectricalDRCCount ::COrDRCTclInterface_GetPhysicalDRCCount} {if {![llength [info commands $command]]} {error capability_unavailable}}
    if {![info exists ::COrDRCTclInterface_DRC_ERROR] || ![info exists ::COrDRCTclInterface_DRC_WARNING]} {error capability_unavailable}
    if {$::COrDRCTclInterface_DRC_ERROR!=0 || $::COrDRCTclInterface_DRC_WARNING!=1} {error invalid_drc_counts}
    set design [GetActivePMDesign]
    if {$design eq "NULL" || $design eq ""} {error target_changed}
    # The native index key is not a filesystem path to normalize: preserve exact GetName spelling.
    set key [DboTclHelper_sMakeStdStr [nameOf $design]]
    set fields {}
    foreach method {GetElectricalDRCCount GetPhysicalDRCCount} category {electrical physical} {
        foreach severity {DRC_ERROR DRC_WARNING} label {Errors Warnings} {
            set value [::COrDRCTclInterface_$method $key [set ::COrDRCTclInterface_$severity]]
            if {![string is integer -strict $value] || $value<0 || $value>2147483647} {error invalid_drc_counts}
            lappend fields $category$label $value
        }
    }
    return [cmcp::obj {*}$fields]
}
proc ::cmcpBridge::rpcReply {request status data {code ""}} {
    variable config; variable generation
    return [cmcp::obj protocol 2 requestId [cmcp::q [dict get $request requestId]] instanceId [cmcp::q [dict get $config instanceId]] pid [pid] generation $generation status [cmcp::q $status] code [cmcp::q $code] data $data]
}
proc ::cmcpBridge::rpc {request} {
    variable config; variable generation; variable sessions; variable lost; variable propertyPlans
    if {[lsort [dict keys $request]] ne {deadlineMs expectedDesign instanceId operation params protocol requestId token}} {error "invalid fields"}
    if {[dict get $request token] ne [dict get $config token]} {error "authentication failed"}
    if {[dict get $request instanceId] ne [dict get $config instanceId] || [pid] != [dict get $config expectedPid]} {error "wrong instance"}
    if {![string equal -nocase [file normalize [dict get $request expectedDesign]] [dict get $config expectedDesign]]} {error "wrong binding"}
    if {![regexp {^[a-f0-9]{32}$} [dict get $request requestId]]} {error "invalid request id"}
    set deadline [dict get $request deadlineMs]
    if {![string is wideinteger -strict $deadline] || $deadline < [clock milliseconds] || $deadline > [expr {[clock milliseconds]+10000}]} {
        return [rpcReply $request failed [cmcp::obj] deadline_exceeded]
    }
    set operation [dict get $request operation]
    set params [dict get $request params]
    if {[catch {dict size $params}]} {error "invalid params"}
    lassign [observe] path dirty
    if {$operation eq "hello"} {
        if {[dict size $params]} {error "extra params"}
        set caps [list [cmcp::q status] [cmcp::q pages] [cmcp::q selection]]
        if {[llength [info commands ::COrDRCTclInterface_GetElectricalDRCCount]] && [llength [info commands ::COrDRCTclInterface_GetPhysicalDRCCount]] && [info exists ::COrDRCTclInterface_DRC_ERROR] && [info exists ::COrDRCTclInterface_DRC_WARNING]} {lappend caps [cmcp::q drc_counts]}
        if {[llength [info commands ::capGetDRCConfigData]] && [llength [info commands ::capIsOnlineDrcEnabled]] && [llength [info commands ::COrDRCTclInterface_sIsDRCFlowEnabled]]} {lappend caps [cmcp::q drc_configuration]}
        set writable [expr {[dict exists $config allowPropertyWrite] && [dict get $config allowPropertyWrite]}]
        if {$writable} {lappend caps [cmcp::q property.plan] [cmcp::q property.apply] [cmcp::q property.outcome]}
        return [rpcReply $request succeeded [cmcp::obj activeDesign [cmcp::q $path] dirtyState [cmcp::q $dirty] bindingLost [expr {$lost ? "true" : "false"}] executable [cmcp::q [file normalize [info nameofexecutable]]] tclVersion [cmcp::q [info patchlevel]] capabilities [cmcp::arr $caps] writable [expr {$writable ? "true" : "false"}] sessionCount [dict size $sessions] propertyPlanCount [dict size $propertyPlans] observerMode [cmcp::q polling_and_registered_events]]]
    }
    if {$lost} {return [rpcReply $request failed [cmcp::obj] target_changed]}
    # Sessions expire and cannot be resurrected by reconnecting the TCP channel.
    dict for {sid session} $sessions {
        if {[dict get $session expires] < [clock milliseconds]} {dict unset sessions $sid}
    }
    if {$operation eq "session.open"} {
        if {[lsort [dict keys $params]] ni {{generation sessionId} {access generation sessionId}} || [dict get $params generation] ne $generation || ![regexp {^[a-f0-9]{32}$} [dict get $params sessionId]]} {
            return [rpcReply $request failed [cmcp::obj] stale_generation]
        }
        set access read
        if {[dict exists $params access]} {set access [dict get $params access]}
        if {$access ni {read write}} {error "invalid access"}
        if {$access eq "write" && (![dict exists $config allowPropertyWrite] || ![dict get $config allowPropertyWrite] || $dirty ne "clean")} {return [rpcReply $request failed [cmcp::obj] write_denied]}
        if {[dict size $sessions] >= 16} {return [rpcReply $request failed [cmcp::obj] session_limit]}
        set sid [dict get $params sessionId]
        if {[dict exists $sessions $sid]} {return [rpcReply $request failed [cmcp::obj] session_conflict]}
        dict set sessions $sid [dict create access $access generation $generation expires [expr {[clock milliseconds]+600000}]]
        return [rpcReply $request succeeded [cmcp::obj sessionId [cmcp::q $sid] readOnly [expr {$access eq "read" ? "true" : "false"}] leaseSeconds 600]]
    }
    if {$operation in {property.plan property.apply property.outcome property.abandon property.ack}} {
        set rc [catch {propertyOperation $request $path $dirty} result]
        if {$rc} {
            if {$result ni {object_not_found ambiguous_target dbo_error result_limit}} {set result dbo_error}
            return [rpcReply $request failed [cmcp::obj] $result]
        }
        return $result
    }
    if {[lsort [dict keys $params]] ne {generation sessionId}} {error "invalid session params"}
    set sid [dict get $params sessionId]
    if {![dict exists $sessions $sid] || [dict get $params generation] ne $generation} {return [rpcReply $request failed [cmcp::obj] session_lost]}
    dict set sessions $sid expires [expr {[clock milliseconds]+600000}]
    if {$operation eq "session.close"} {dict unset sessions $sid; return [rpcReply $request succeeded [cmcp::obj closed true]]}
    if {$operation ni {status pages selection drc_configuration drc_counts}} {return [rpcReply $request failed [cmcp::obj] capability_unavailable]}
    set before $generation
    set rc [catch {
        switch -- $operation {
            status {set data [cmcp::obj activeDesign [cmcp::q $path] dirtyState [cmcp::q $dirty] readOnly [expr {[dict get $sessions $sid access] eq "read" ? "true" : "false"}]]}
            drc_configuration {set data [drc_configuration]}
            drc_counts {set data [drc_counts]}
            pages {set data [pages]}
            selection {set data [selection [dict get $request requestId]]}
        }
    } message]
    observe
    if {$before != $generation || $lost} {return [rpcReply $request failed [cmcp::obj] session_lost]}
    if {[clock milliseconds] > $deadline} {return [rpcReply $request failed [cmcp::obj] deadline_exceeded]}
    if {$rc} {
        if {$message ni {result_limit no_active_page target_changed dbo_error capability_unavailable invalid_drc_configuration invalid_drc_counts}} {set message dbo_error}
        return [rpcReply $request failed [cmcp::obj] $message]
    }
    return [rpcReply $request succeeded $data]
}

source [file join [file dirname [info script]] bridge_property.tcl]
