# Read fresh typed vector descriptors, scoped by package/device/part view.
source [file join [file dirname [info script]] json.tcl]
source [file join [file dirname [info script]] dbo_part_signature.tcl]
if {$argc!=3 && $argc!=6} {exit 2}
lassign $argv root library output wantedPackage wantedDevice wantedPart
proc cmcp::cs {v} {return [DboTclHelper_sMakeCString $v]}
proc cmcp::str {v} {return [DboTclHelper_sGetConstCharPtr $v]}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_state_[$s Code]"}}
source [file join [file dirname [info script]] dbo_vector_json.tcl]
set session ""
set rc [catch {
 load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set state [DboState];set lib [$session GetLibAndSchematics [cmcp::cs $library] $state];cmcp::check $state
 set rows {};set count 0;set packages [$lib NewPackagesIter $state];cmcp::check $state
 try {
  for {set package [$packages NextPackage $state]} {$package ne "NULL"} {set package [$packages NextPackage $state]} {
   cmcp::check $state;set pkgname [cmcp::cs ""];cmcp::check [$package GetName $pkgname]
   if {$argc==6 && [cmcp::str $pkgname] ne $wantedPackage} {continue}
   set it [$package NewDevicesIter $state];cmcp::check $state
   try {
    for {set device [$it NextDevice $state]} {$device ne "NULL"} {set device [$it NextDevice $state]} {
     cmcp::check $state;set designator [cmcp::cs ""];cmcp::check [$device GetDesignator $designator];if {$argc==6 && [cmcp::str $designator] ne $wantedDevice} {continue};set cell [$device GetCell $state];cmcp::check $state
     set parts [$cell NewPartsIter $state];cmcp::check $state
     try {
      for {set part [$parts NextPart $state]} {$part ne "NULL"} {set part [$parts NextPart $state]} {
       cmcp::check $state;if {[incr count]>10000} {error view_limit};set name [cmcp::cs ""];cmcp::check [$part GetName $name]
       if {$argc==6 && [cmcp::str $name] ne $wantedPart} {continue}
       set descriptors {};set vs [DboState];set vectors [$part NewVectorsIter $vs $::IterDefs_ALL];cmcp::check $vs
       try {
        for {set v [$vectors NextVector $vs]} {$v ne "NULL"} {set v [$vectors NextVector $vs]} {cmcp::check $vs;if {[llength $descriptors]>=4096} {error vector_limit};lappend descriptors [cmcp::descriptorJson [cmcp::vectorDescriptor $v]]}
       } finally {delete_DboGraphicObjectVectorsIter $vectors}
       if {[$vs Failed] && [$vs Code]!=1022} {error unexpected_vector_iterator_end}
       set signature [cmcp::partShapeSignature $part]
       lappend rows [cmcp::obj package [cmcp::q [cmcp::str $pkgname]] designator [cmcp::q [cmcp::str $designator]] partName [cmcp::q [cmcp::str $name]] vectors [cmcp::arr $descriptors] signature [cmcp::q $signature]]
      }
     } finally {delete_DboCellPartsIter $parts}
    }
   } finally {delete_DboPackageDevicesIter $it}
  }
 } finally {delete_DboLibPackagesIter $packages}
 set f [open $output {WRONLY CREAT EXCL}];try {fconfigure $f -encoding utf-8 -translation lf;puts -nonewline $f [cmcp::arr $rows]} finally {close $f}
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
if {$rc} {puts stderr "CADENCE_DBO_ERROR: vector descriptor read failed: $message";exit 1}
