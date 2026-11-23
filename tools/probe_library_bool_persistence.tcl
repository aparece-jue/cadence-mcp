# Fixed private library boolean persistence experiment.
lassign $argv install target mode output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set state [DboState]
set lib [$session GetLibAndSchematics [cs $target] $state];ck $state
set it [$lib NewPackagesIter $state];ck $state
set pkg [$it NextPackage $state];ck $state
delete_DboLibPackagesIter $it
set it [$pkg NewPartsIter $state];ck $state
set part [$it NextPart $state];ck $state
delete_DboPackagePartsIter $it
set name [cs ""];ck [$part GetName $name]
set rows {}
foreach {property getter setter} {
 {Pin Names Visible} GetPinNamesAreVisible SetPinNamesAreVisible
 {Pin Numbers Visible} GetPinNumbersAreVisible SetPinNumbersAreVisible
 {Pin Names Rotate} GetPinNamesAreRotated SetPinNamesAreRotated
} {
 set state [DboState];set db [$part GetDBProp [cs $property] $state];ck $state
 set type [$db GetType $state];ck $state
 set before [$part $getter $state];ck $state
 set dbBefore [$db GetBOOLValue $part $state];ck $state
 set attempted false;set code -1;set failed -1
 if {$mode ne "read"} {
  set attempted true
  if {$mode eq "typed"} {
   set value [DboValue]
   set init [$part GetDBPropValue [cs $property] $value];ck $init
   set change [$value SetBOOL [expr {!$before}]]
   set code [$change Code];set failed [$change Failed]
   if {!$failed} {set change [$part SetDBPropValue [cs $property] $value];set code [$change Code];set failed [$change Failed]}
  } elseif {$mode in {setter savepart savesymbol savepackage}} {
   set change [$part $setter [expr {!$before}]]
   set code [$change Code];set failed [$change Failed]
  } else {error invalid_mode}
 }
 set state [DboState];set after [$part $getter $state];ck $state
 set dbAfter [$db GetBOOLValue $part $state];ck $state
 lappend rows [cmcp::obj property [cmcp::q $property] nativeType $type before $before dbBefore $dbBefore attempted $attempted code $code failed $failed after $after dbAfter $dbAfter]
}
if {$mode ne "read"} {
 ck [$part MarkModified];$lib MarkModified $part
 ck [$pkg MarkModified];$lib MarkModified $pkg;ck [$lib MarkModified]
 switch -- $mode {
  savepart {ck [$lib SavePart $part]}
  savesymbol {ck [$lib SaveSymbol $part]}
  savepackage {ck [$lib SavePackageAll $pkg]}
 }
 ck [$session MarkAllLibForSave $lib];ck [$session SaveLib $lib]
}
set f [open $output {WRONLY CREAT EXCL}]
fconfigure $f -encoding utf-8
puts $f [cmcp::obj partName [cmcp::q [DboTclHelper_sGetConstCharPtr $name]] rows [cmcp::arr $rows]]
close $f
delete_DboSession $session
