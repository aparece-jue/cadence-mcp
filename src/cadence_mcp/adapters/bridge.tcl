# External Capture bridge. Source manually; never install into capinit.
# Only fixed allowlisted operations are accepted. No request is evaluated as a script.
package require json
source [file join [file dirname [info script]] json.tcl]
namespace eval ::cmcpBridge {
    variable listener
    variable clients
    if {![info exists listener]} {set listener ""}
    if {![info exists clients]} {set clients [dict create]}
    variable config
    variable endpointFile; if {![info exists endpointFile]} {set endpointFile ""}
    variable busy; if {![info exists busy]} {set busy 0}
}
proc ::cmcpBridge::activeDesign {} {
    set design [GetActivePMDesign]
    if {$design eq "NULL" || $design eq ""} {return ""}
    set name [DboTclHelper_sMakeCString]
    $design GetName $name
    return [file normalize [DboTclHelper_sGetConstCharPtr $name]]
}
proc ::cmcpBridge::closeClient {channel} {
    variable clients
    if {[dict exists $clients $channel]} {
        after cancel [dict get $clients $channel timer]
        dict unset clients $channel
    }
    catch {fileevent $channel readable {}}
    catch {close $channel}
}
proc ::cmcpBridge::stop {} {
    variable listener; variable clients; variable endpointFile; variable config
    if {[llength [info commands ::cmcpBridge::lifecycleStop]]} {lifecycleStop}
    foreach channel [dict keys $clients] {closeClient $channel}
    if {$listener ne ""} {catch {close $listener}; set listener ""}
    if {$endpointFile ne "" && [file exists $endpointFile]} {
        catch {
            set f [open $endpointFile];try {set old [::json::json2dict [read $f 16385]]} finally {close $f}
            if {[dict get $old pid]==[pid] && [dict get $old instanceId] eq [dict get $config instanceId]} {file delete $endpointFile}
        }
    }
    set endpointFile ""
}
proc ::cmcpBridge::accept {channel address port} {
    variable clients
    if {$address ne "127.0.0.1" || [dict size $clients] >= 4} {close $channel; return}
    fconfigure $channel -blocking 0 -buffering none -encoding binary -translation binary
    dict set clients $channel [dict create bytes "" timer [after 3000 [list ::cmcpBridge::closeClient $channel]]]
    fileevent $channel readable [list ::cmcpBridge::readRequest $channel]
}
proc ::cmcpBridge::readRequest {channel} {
    variable clients; variable busy; variable config
    if {![dict exists $clients $channel]} {return}
    set bytes [dict get $clients $channel bytes]
    if {[catch {append bytes [read $channel 4096]}] || [string length $bytes] > 16384} {closeClient $channel; return}
    set newline [string first "\n" $bytes]
    if {$newline < 0} {
        if {[eof $channel]} {closeClient $channel; return}
        dict set clients $channel bytes $bytes
        return
    }
    if {[catch {
        if {$newline != [expr {[string length $bytes]-1}]} {error "multiple frames"}
        fileevent $channel readable {}
        set document [encoding convertfrom utf-8 [string range $bytes 0 $newline-1]]
        if {![::json::validate $document]} {error "invalid json"}
        set request [::json::json2dict $document]
        if {$busy} {
            if {[dict get $request protocol]!=2 || [dict get $request token] ne [dict get $config token] || [dict get $request instanceId] ne [dict get $config instanceId]} {error "authentication failed"}
            set response [rpcReply $request failed [cmcp::obj] bridge_busy]
        } else {
            set busy 1
            try {set response [::cmcpBridge::dispatch $request]} finally {set busy 0}
        }
        if {[string bytelength $response] > 16384} {
            if {[dict get $request protocol] != 2} {error "result too large"}
            set response [::cmcpBridge::rpcReply $request failed [cmcp::obj] result_limit]
        }
        puts -nonewline $channel [encoding convertto utf-8 "$response\n"]
        flush $channel
    }]} {closeClient $channel; return}
    closeClient $channel
}
proc ::cmcpBridge::dispatch {request} {
    variable config
    if {[dict exists $request protocol] && [dict get $request protocol] eq "2"} {return [rpc $request]}
    set fields {expectedDesign instanceId operation protocol requestId token}
    if {[lsort [dict keys $request]] ne $fields} {error "invalid fields"}
    if {[dict get $request token] ne [dict get $config token]} {error "authentication failed"}
    if {[dict get $request protocol] ne "1" || [dict get $request operation] ne "status"} {error "unsupported operation"}
    if {[dict get $request instanceId] ne [dict get $config instanceId]} {error "wrong instance"}
    if {[pid] != [dict get $config expectedPid]} {error "wrong process"}
    set expected [dict get $config expectedDesign]
    if {![string equal -nocase [file normalize [dict get $request expectedDesign]] $expected]} {error "wrong binding"}
    set actual [activeDesign]
    set matched [string equal -nocase $expected $actual]
    set requestId [dict get $request requestId]
    if {[string length $requestId] > 100} {error "invalid request identity"}
    # Active path mismatch is explicit; never retarget to the newly active design.
    set status [expr {$matched ? "succeeded" : "target_changed"}]
    return [cmcp::obj protocol 1 requestId [cmcp::q $requestId] instanceId [cmcp::q [dict get $config instanceId]] pid [pid] status [cmcp::q $status] activeDesign [cmcp::q $actual] tclVersion [cmcp::q [info patchlevel]] readOnly true dirtyState [cmcp::q unknown] capabilities [cmcp::arr [list [cmcp::q gui.status]]]]
}
proc ::cmcpBridge::start {configFile} {
    variable listener; variable config; variable endpointFile
    if {$listener ne ""} {error "Bridge already running; explicitly stop it before restart"}
    set stream [open $configFile r]
    try {
        fconfigure $stream -encoding utf-8
        set bytes [read $stream 16385]
    } finally {close $stream}
    if {[string length $bytes] > 16384} {error "Configuration too large"}
    set config [::json::json2dict $bytes]
    dict set config expectedDesign [file normalize [dict get $config expectedDesign]]
    if {[pid] != [dict get $config expectedPid]} {error "Configuration belongs to another Capture process"}
    if {![string equal -nocase [activeDesign] [dict get $config expectedDesign]]} {error "Wrong active design"}
    if {[string length [dict get $config token]] != 64} {error "Invalid token"}
    set endpoint [file join [file dirname [file normalize $configFile]] endpoint.json]
    if {[file exists $endpoint]} {error "Endpoint descriptor exists; prepare a fresh private directory"}
    set temporary [file join [file dirname $endpoint] ".endpoint-[pid]-[clock clicks].tmp"]
    set listener [socket -server ::cmcpBridge::accept -myaddr 127.0.0.1 0]
    set port [lindex [fconfigure $listener -sockname] end]
    if {[catch {
        set stream [open $temporary {WRONLY CREAT EXCL}]
        try {
            fconfigure $stream -encoding utf-8 -translation lf
            puts $stream [cmcp::obj protocol 1 host [cmcp::q 127.0.0.1] port $port pid [pid] instanceId [cmcp::q [dict get $config instanceId]]]
        } finally {close $stream}
        # Publish only a complete closed descriptor. Do not overwrite a peer.
        file rename -- $temporary $endpoint
        set endpointFile $endpoint
    } message]} {
        catch {file delete -- $temporary}
        stop; error "Cannot publish endpoint descriptor"
    }
    lifecycleStart
    puts "CADENCE_BRIDGE_READY authenticated_sessions"
}

source [file join [file dirname [info script]] bridge_rpc.tcl]
