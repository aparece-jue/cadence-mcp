# Fixed dedicated digital reader. Never use getDigital with an unlisted axis/missing name.
if {$argc!=7} {exit 2};lassign $argv install data output mode block trace helper
source $helper
set created 0;set phase load_dll
set rc [catch {
 load [file join $install tools bin orPIOData64.dll]
 if {![llength [info commands ::orPIOObject_getDigital]] || $mode ne "digital_trace"} {error digital_method_unavailable}
 orPIOObject reader;set created 1;set phase load_file
 if {![reader loadFile $data]} {error load_failed}
 set count [reader getNumberofBlocks]
 if {![string is integer -strict $count] || $count<1 || $count>128 || ![string is integer -strict $block] || $block<0 || $block>=$count} {error block_limit}
 if {![reader setBlock $block]} {error select_block_failed}
 set type [reader getHeaderData DataType];set rows [reader getHeaderData NumberofDigitalRows];set columns [reader getHeaderData NumberofDigitalColumns]
 if {$type ni {1 2} || ![string is integer -strict $rows] || $rows<1 || $rows>100000 || ![string is integer -strict $columns] || $columns<1 || $columns>10000 || [reader getHeaderData PrimaryParamName] ne "Time" || [reader getHeaderData AnalysisName] ne "Transient Analysis"} {error unsupported_digital_block}
 set phase validate_digital_directory;set names [reader getDataNames 1]
 if {[string length $names]>16777216 || [llength $names]!=$columns} {error digital_directory_mismatch}
 set canonical {};foreach group $names {set name [lindex [split $group {;}] 0];if {[string length $name]<1 || [string length $name]>512} {error digital_name_limit};lappend canonical $name}
 if {[llength [lsearch -all -exact $canonical $trace]]!=1} {error trace_not_found}
 set phase read_digital_trace;set value [reader getDigital $trace]
 if {[string length $value]>16777216} {error result_limit}
 set result [cmcp::obj block $block trace [cmcp::q $trace] blockDigitalRows $rows nativeDigitalData [cmcp::q $value]]
 set phase close_reader;set created 0;set closed [reader close]
 if {![string is boolean -strict $closed] || !$closed} {error close_failed}
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts $f $result} finally {close $f}
} message]
if {$created} {set created 0;catch {reader close}}
if {$rc} {
 if {![file exists $output]} {set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts $f [cmcp::obj error [cmcp::q native_digital_failure] phase [cmcp::q $phase]];close $f}
 exit 1
}
