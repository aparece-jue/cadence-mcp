# Self-authored command-registration probe; no session or design is opened.
set root [lindex $argv 0]
puts "CMCP:tclVersion=[info patchlevel]"
puts "CMCP:pointerSize=$::tcl_platform(pointerSize)"
set rc [catch {load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic} message]
puts "CMCP:loadCatch=$rc"
puts "CMCP:dboCreateSession=[llength [info commands DboTclHelper_sCreateSession]]"
puts "CMCP:activePage=[llength [info commands GetActivePage]]"
if {$rc} {puts stderr "CADENCE_DBO_ERROR: extension load failed"; exit 1}
