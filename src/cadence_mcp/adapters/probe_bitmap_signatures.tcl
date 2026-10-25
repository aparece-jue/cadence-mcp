source [file join [file dirname [info script]] json.tcl]
if {$argc!=2} {exit 2}
lassign $argv root output
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set rows {}
set code [catch {DboTclHelper_sMakeBitmap} message];lappend rows [cmcp::obj command [cmcp::q DboTclHelper_sMakeBitmap] status $code message [cmcp::q $message]]
set code [catch {DboTclHelper_sMakeBitMapData} message];lappend rows [cmcp::obj command [cmcp::q DboTclHelper_sMakeBitMapData] status $code message [cmcp::q $message]]
set code [catch {DboTclHelper_sGetBase64BitmapForOle} message];lappend rows [cmcp::obj command [cmcp::q DboTclHelper_sGetBase64BitmapForOle] status $code message [cmcp::q $message]]
set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
