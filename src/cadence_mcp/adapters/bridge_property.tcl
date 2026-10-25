# One fixed metadata property; writes require a host-created isolated fixture lease.
source [file join [file dirname [info script]] property_api.tcl]
namespace eval ::cmcpBridge {variable propertyPlans; if {![info exists propertyPlans]} {set propertyPlans [dict create]}}
proc ::cmcpBridge::propertyOperation {request path dirty} {
    variable config;variable generation;variable sessions;variable propertyPlans
    set params [dict get $request params];set operation [dict get $request operation]
    if {![dict exists $config allowPropertyWrite] || ![dict get $config allowPropertyWrite]} {
        return [rpcReply $request failed [cmcp::obj] capability_unavailable]
    }
    if {$operation in {property.outcome property.abandon property.ack}} {
        if {[dict keys $params] ne {planId}} {error "invalid outcome params"}
        set planId [dict get $params planId]
        if {![dict exists $propertyPlans $planId]} {return [rpcReply $request failed [cmcp::obj] unknown_outcome]}
        set plan [dict get $propertyPlans $planId]
        if {$operation eq "property.ack"} {
            if {[dict get $plan state] ni {saved cancelled}} {return [rpcReply $request failed [cmcp::obj] state_indeterminate]}
            dict unset propertyPlans $planId
            return [rpcReply $request succeeded [cmcp::obj released true]]
        }
        set expectedGeneration [dict get $plan generation]
        if {[dict exists $plan savedGeneration]} {set expectedGeneration [dict get $plan savedGeneration]}
        set unchanged [expr {$expectedGeneration==$generation}]
        if {$operation eq "property.abandon"} {
            if {[dict get $plan state] ne "planned" || !$unchanged || $dirty ne "clean"} {return [rpcReply $request failed [cmcp::obj] state_indeterminate]}
            dict set propertyPlans $planId state cancelled
            invalidate
            return [rpcReply $request succeeded [cmcp::obj abandoned true designChanged false]]
        }
        return [rpcReply $request succeeded [cmcp::obj state [cmcp::q [dict get $plan state]] unchangedGeneration [expr {$unchanged ? "true" : "false"}] dirtyState [cmcp::q $dirty]]]
    }
    if {![dict exists $params sessionId] || ![dict exists $params generation]} {error "missing session"}
    set sid [dict get $params sessionId]
    if {![dict exists $sessions $sid] || [dict get $params generation] ne $generation} {return [rpcReply $request failed [cmcp::obj] session_lost]}
    if {[dict get $sessions $sid access] ne "write"} {return [rpcReply $request failed [cmcp::obj] write_access_required]}
    if {$dirty ne "clean"} {return [rpcReply $request failed [cmcp::obj] dirty_design]}
    set design [GetActivePMDesign]
    if {$operation eq "property.plan"} {
        if {[lsort [dict keys $params]] ne {generation pageName planId reference schematicName sessionId value}} {error "invalid property plan"}
        set planId [dict get $params planId]
        if {![regexp {^[a-f0-9]{32}$} $planId] || [string length [dict get $params value]]>512} {error "invalid property value"}
        dict for {key pending} $propertyPlans {
            if {[dict get $pending state] eq "planned" && [dict get $pending expires]<[clock milliseconds]} {dict unset propertyPlans $key}
        }
        if {[dict size $propertyPlans]>=64} {return [rpcReply $request failed [cmcp::obj] plan_limit]}
        lassign [::cmcpProperty::find $design [dict get $params schematicName] [dict get $params pageName] [dict get $params reference]] schematic page part
        lassign [::cmcpProperty::read $part] exists old
        dict set propertyPlans $planId [dict merge $params [dict create oldExists $exists oldValue $old state planned expires [expr {[clock milliseconds]+60000}]]]
        return [rpcReply $request succeeded [cmcp::obj planId [cmcp::q $planId] property [cmcp::q MCP_NOTE] oldExists [expr {$exists ? "true" : "false"}] oldValue [cmcp::q $old] newValue [cmcp::q [dict get $params value]]]]
    }
    if {[lsort [dict keys $params]] ne {generation leaseId planId sessionId}} {error "invalid property apply"}
    if {[dict get $params leaseId] ne [dict get $config writeLeaseId]} {error "wrong write lease"}
    set planId [dict get $params planId]
    if {![dict exists $propertyPlans $planId]} {return [rpcReply $request failed [cmcp::obj] stale_plan]}
    set plan [dict get $propertyPlans $planId]
    if {[dict get $plan state] ne "planned"} {return [rpcReply $request failed [cmcp::obj] state_indeterminate]}
    if {[dict get $plan generation] ne $generation || [dict get $plan sessionId] ne $sid || [dict get $plan expires]<[clock milliseconds]} {return [rpcReply $request failed [cmcp::obj] stale_plan]}
    lassign [::cmcpProperty::find $design [dict get $plan schematicName] [dict get $plan pageName] [dict get $plan reference]] schematic page part
    if {[::cmcpProperty::read $part] ne [list [dict get $plan oldExists] [dict get $plan oldValue]]} {return [rpcReply $request failed [cmcp::obj] stale_plan]}
    if {[clock milliseconds]>[dict get $request deadlineMs]} {return [rpcReply $request failed [cmcp::obj] deadline_exceeded]}
    dict set propertyPlans $planId state started
    set rc [catch {
        ::cmcpProperty::check [$part SetEffectivePropStringValue [::cmcpProperty::cs MCP_NOTE] [::cmcpProperty::cs [dict get $plan value]]]
        ::cmcpProperty::save $design $schematic $page
        if {[::cmcpProperty::read $part] ne [list 1 [dict get $plan value]]} {error "property mismatch"}
    } message]
    invalidate
    if {$rc} {
        dict set propertyPlans $planId state indeterminate
        return [rpcReply $request failed [cmcp::obj] state_indeterminate]
    }
    dict set propertyPlans $planId state saved
    dict set propertyPlans $planId savedGeneration $generation
    return [rpcReply $request succeeded [cmcp::obj planId [cmcp::q $planId] appliedInMemory true saved true reopenVerified false connectivityVerified false]]
}
