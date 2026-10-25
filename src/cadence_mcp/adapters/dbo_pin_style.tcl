# Fixed documented DboSymbolPin flags, read in the isolated database process.
proc cmcp::pinStyle {pin} {
 set st [DboState];set flags {}
 foreach {key method} {long GetIsLong clock GetIsClock dot GetIsDot leftPointing GetIsLeftPointing rightPointing GetIsRightPointing netStyle GetIsNetStyle noConnect GetIsNoConnect visible GetIsVisible global GetIsGlobal numberVisible GetIsNumberVisible userDefinedShape GetIsUserDefinedShape} {
  set value [$pin $method $st];cmcp::check $st
  if {$value ni {0 1}} {error non_boolean_pin_style}
  dict set flags $key $value
 }
 return $flags
}
proc cmcp::styleJson {flags} {
 set fields {}
 dict for {key value} $flags {
  if {$value} {set encoded true} else {set encoded false}
  lappend fields $key $encoded
 }
 return [cmcp::obj {*}$fields]
}
