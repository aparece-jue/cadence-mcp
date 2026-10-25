package require json
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_package_properties.tcl]
if {$argc!=3} {exit 2}
lassign $argv root target output
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set phase opening
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState]
 set lib [$session GetLibAndSchematics [cmcp::cs $target] $state];cmcp::check $state
 set pkg [$lib GetPackage [cmcp::cs MCP_SECOND] $state];cmcp::check $state
 set before [cmcp::packagePropertyDict $pkg]
 set phase user_property
 set prop [$pkg NewUserProp [cmcp::cs MCP_NOTE] [cmcp::cs "package note 中文\nline2"] $state];cmcp::check $state
 if {$prop eq "NULL"} {error no_new_user_property}
 set phase fixed_fields
 cmcp::check [$pkg SetReferenceTemplate [cmcp::cs J?]]
 cmcp::check [$pkg SetPCBFootprint [cmcp::cs "PKG_51"]]
 cmcp::check [$pkg SetPCBLib [cmcp::cs "PCB_LIB_51"]]
 set after [cmcp::packagePropertyDict $pkg]
 set phase save;cmcp::check [$session MarkAllLibForSave $lib];cmcp::check [$session SaveLib $lib]
 set result [cmcp::obj saved true before [cmcp::packagePropertiesJson $before] after [cmcp::packagePropertiesJson $after]]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {set result [cmcp::obj saved false phase [cmcp::q $phase] message [cmcp::q $message]]}
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f $result} finally {close $f}
if {$rc} {exit 1}
