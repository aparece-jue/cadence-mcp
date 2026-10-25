# Fixed PSpice direct data reader. Arguments are literal values, never evaluated.
if {$argc != 7} {error "install copied-dat output mode block trace json-helper"}
lassign $argv install data output mode block trace helper
source $helper
# Digital native names contain semicolon-separated aliases inside each Tcl list item.
proc cmcp::digitalNames {names expected} {
    if {[llength $names]!=$expected} {error digital_name_count_mismatch}
    set rows {};set total 0
    foreach group $names {
        set tokens [split $group {;}];set canonical [lindex $tokens 0];set aliases {}
        foreach name $tokens {
            if {[incr total]>100000 || [string length $name]==0 || [string length $name]>512} {error digital_name_limit}
            if {$name ne $canonical && $name ni $aliases} {lappend aliases $name}
        }
        if {[llength $aliases]} {lappend rows [cmcp::obj $canonical [cmcp::arr [lmap a $aliases {cmcp::q $a}]]]} else {lappend rows [cmcp::q $canonical]}
    }
    return [cmcp::arr $rows]
}
set phase load_dll
set created 0
set rc [catch {
    load [file join $install tools bin orPIOData64.dll]
    set phase create_reader
    orPIOObject reader
    set created 1
    set phase load_file
    if {![reader loadFile $data]} {error "load_failed"}
    set phase count_blocks
    set count [reader getNumberofBlocks]
    if {![string is integer -strict $count] || $count < 1 || $count > 128} {error "block_limit"}
    if {$mode eq "headers"} {
        set phase headers
        set header [reader getJSON]
        if {[string length $header] > 16777216} {error "header_limit"}
        set result [cmcp::obj blockCount $count headerJSON [cmcp::q $header]]
    } elseif {$mode eq "headers_direct"} {
        set phase direct_headers
        set blocks {};set total 0
        for {set b 0} {$b<$count} {incr b} {
            if {![reader setBlock $b]} {error block_failed}
            set attrs [list Number $b]
            foreach key {ComplexFlag DataType NumberofAnalogRows NumberofAnalogColumns} {
                set value [reader getHeaderData $key]
                if {![string is integer -strict $value]} {error invalid_header_integer}
                lappend attrs $key $value
            }
            foreach key {PrimaryParamName AnalysisName} {lappend attrs $key [cmcp::q [reader getHeaderData $key]]}
            set dataType [reader getHeaderData DataType]
            set analogColumns [reader getHeaderData NumberofAnalogColumns]
            if {$analogColumns==0} {set names {}} else {set names [reader getDataNames 0]}
            if {[string length $names]>16777216} {error names_limit}
            set traceNames {}
            foreach name $names {
                if {[incr total]>100000 || [string length $name]>512} {error trace_limit}
                lappend traceNames [cmcp::q $name]
            }
            set nameArgs [list {Analog Names} [cmcp::arr $traceNames]]
            if {$dataType in {1 2}} {
                foreach key {NumberofDigitalRows NumberofDigitalColumns} {
                    set value [reader getHeaderData $key]
                    if {![string is integer -strict $value]} {error invalid_digital_header_integer}
                    lappend attrs $key $value
                }
                set digitalColumns [reader getHeaderData NumberofDigitalColumns]
                if {$digitalColumns<0 || $digitalColumns>10000} {error digital_column_limit}
                set digitalNames [reader getDataNames 1]
                if {[string length $digitalNames]>16777216} {error digital_names_limit}
                lappend nameArgs {Digital Names} [cmcp::digitalNames $digitalNames $digitalColumns]
            }
            lappend attrs {Trace Names} [cmcp::obj {*}$nameArgs]
            lappend blocks [cmcp::obj {*}$attrs]
        }
        set header [cmcp::arr $blocks]
        if {[string length $header]>16777216} {error header_limit}
        set result [cmcp::obj blockCount $count headerJSON [cmcp::q $header]]
    } elseif {$mode eq "trace"} {
        set phase select_block
        if {![string is integer -strict $block] || $block < 0 || $block >= $count} {error "bad_block"}
        if {![reader setBlock $block]} {error "block_failed"}
        set rows [reader getHeaderData NumberofAnalogRows]
        if {![string is integer -strict $rows] || $rows < 0 || $rows > 100000} {error "row_limit"}
        set phase read_trace
        set values [reader get $trace]
        if {[string length $values] > 16777216} {error "trace_limit"}
        set result [cmcp::obj block $block trace [cmcp::q $trace] rows $rows valuesCSV [cmcp::q $values]]
    } else {error "unsupported_mode"}
    set phase close_reader
    # Native close is not idempotent on the observed digital reader. Never retry it.
    set created 0
    set closed [reader close]
    if {![string is boolean -strict $closed] || !$closed} {error "close_failed"}
    set phase write_result
    set channel [open $output {WRONLY CREAT EXCL}]
    try {fconfigure $channel -encoding utf-8 -translation lf; puts -nonewline $channel $result} finally {close $channel}
} message options]
if {$created} {catch {reader close}}
if {$rc} {
    if {![file exists $output]} {
        set failed [open $output {WRONLY CREAT EXCL}]
        fconfigure $failed -encoding utf-8 -translation lf
        puts -nonewline $failed [cmcp::obj error [cmcp::q native_dat_failure] phase [cmcp::q $phase]]
        close $failed
    }
    exit 1
}
