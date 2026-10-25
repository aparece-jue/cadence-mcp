# Fixed native-id-bound display-font write, all other display attributes left intact.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_vector_signature.tcl]
source [file join [file dirname [info script]] dbo_qualified_page.tcl]
package require json
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
lassign $argv install design request output
set session "";set phase request
set rc [catch {
 if {[file size $request]>16384} {error request_limit}
 set f [open $request];try {fconfigure $f -encoding utf-8;set spec [json::json2dict [read $f 16385]]} finally {close $f}
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 set phase locate;lassign [cmcp::qualifiedPage $d [dict get $spec schematicName] [dict get $spec pageName]] s page
 set it [$page NewPartInstsIter $st];cmcp::check $st;set found {};set count 0
 try {
  for {set part [$it NextPartInst $st]} {$part ne "NULL"} {set part [$it NextPartInst $st]} {
   cmcp::check $st;if {[incr count]>100000} {error object_limit}
   set id [$part GetId $st];cmcp::check $st;if {$id==[dict get $spec nativeId]} {lappend found $part}
  }
 } finally {delete_DboPagePartInstsIter $it}
 if {[llength $found]!=1} {error ambiguous_native_instance}
 set instance [lindex $found 0];set ref [cmcp::cs ""];cmcp::check [$instance GetReference $ref]
 if {[cmcp::str $ref] ne [dict get $spec reference]} {error changed_reference}
 set prop [$instance GetDisplayProp [cmcp::cs [dict get $spec property]] $st];cmcp::check $st
 if {$prop eq "NULL"} {error missing_display}
 set old [DboDisplayProp_sGetFont $prop $st];cmcp::check $st
 if {[cmcp::vectorFont $old] ne [dict get $spec oldFont]} {error changed_font}
 set isDefault [$prop IsFontDefault $st];cmcp::check $st;set defaultType [$prop GetDefaultFontType $st];cmcp::check $st
 if {$isDefault!=[dict get $spec oldFontDefault] || $defaultType!=[dict get $spec oldDefaultFontType]} {error changed_font_inheritance}
 set phase font;set font [DboTclHelper_sMakeLOGFONT {*}[dict get $spec newFont]];cmcp::check [$prop SetFont $font]
 $prop SetBoundingBoxDirty 1;$prop SetOwnerBoundingBoxDirty 1
 set phase save;cmcp::check [$page MarkModified];cmcp::check [$s MarkModified $page];cmcp::check [$s SavePage $page];cmcp::check [$d SaveSchematic $s];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::obj saved [expr {$rc?"false":"true"}] phase [cmcp::q $phase] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
