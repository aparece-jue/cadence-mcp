# Fixed-method native object iterators. Status objects live only in the bounded worker.
# ORDBDLL-1022 is "At normal end of iteration", accepted only with a NULL result.
namespace eval ::cmcp {}
proc ::cmcp::next_object {iterator method} {
 if {$method ni {NextView NextPage NextWire NextPort}} {error unsupported_iterator_method}
 set state [DboState]
 set object [$iterator $method $state]
 if {$object eq ""} {error invalid_iterator_result}
 if {[$state Failed]} {
  if {$object eq "NULL" && [$state Code]==1022} {return NULL}
  error "iterator_failed_[$state Code]"
 }
 return $object
}
