proc cmcp::numberArray {values} {return [cmcp::arr $values]}
proc cmcp::descriptorJson {v} {
 set kind [lindex $v 0]
 switch -- $kind {
  line {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lindex $v 1]] [cmcp::arr [lindex $v 2]] {*}[lrange $v 3 end]]]}
  box - ellipse {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lindex $v 1]] {*}[lrange $v 2 end]]]}
  arc {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lindex $v 1]] [cmcp::arr [lindex $v 2]] [cmcp::arr [lindex $v 3]] {*}[lrange $v 4 end]]]}
  polygon - polyline - bezier {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lmap p [lindex $v 1] {cmcp::arr $p}]] {*}[lrange $v 2 end]]]}
  fill {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lindex $v 1]] {*}[lrange $v 2 end]]]}
  text {set font [lindex $v 4];return [cmcp::arr [list [cmcp::q $kind] [cmcp::q [lindex $v 1]] [cmcp::arr [lindex $v 2]] [cmcp::arr [lindex $v 3]] [cmcp::arr [list [cmcp::q [lindex $font 0]] {*}[lrange $font 1 end]]] [lindex $v 5]]]}
  bitmap {return [cmcp::arr [list [cmcp::q $kind] [cmcp::arr [lindex $v 1]] [cmcp::arr [lindex $v 2]] [cmcp::arr [lindex $v 3]] [lindex $v 4] [cmcp::q [lindex $v 5]]]]}
  default {error unsupported_descriptor_kind}
 }
}
