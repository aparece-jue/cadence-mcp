# Status objects are scoped to a bounded isolated worker, like existing readers.
# The candidate using raw delete_DboState failed real DLL validation. This
# reader retains the established worker-scoped lifetime; OS cleanup follows exit.
namespace eval ::cmcp {}
proc ::cmcp::pin_net {pin} {
    set status [DboState]
    set net [$pin GetNet $status]
    if {$net eq "NULL"} {
        if {[$status Failed] && [$status Code] != 1021} {error "pin_net_lookup_failed"}
        return [list false ""]
    }
    if {[$status Failed]} {error "pin_net_lookup_failed"}
    set status [DboState]
    set name [DboTclHelper_sGetConstCharPtr [DboPortInst_sGetNetName $pin $status]]
    if {[$status Failed]} {error "pin_net_name_failed"}
    return [list true $name]
}
