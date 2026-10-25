# Minimal typed JSON construction for bounded adapter responses.
namespace eval ::cmcp {}
proc ::cmcp::q {value} {
    set out {"}
    foreach char [split $value ""] {
        scan $char %c n
        switch -- $n {
            34 {append out {\"}}
            92 {append out {\\}}
            default {
                if {$n < 32} {append out [format {\u%04x} $n]} else {append out $char}
            }
        }
    }
    append out {"}
    return $out
}
proc ::cmcp::obj {args} {
    set fields {}
    foreach {key value} $args {lappend fields "[cmcp::q $key]:$value"}
    return "\{[join $fields ,]\}"
}
proc ::cmcp::arr {values} {return "\[[join $values ,]\]"}
