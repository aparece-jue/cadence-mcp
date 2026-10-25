"""Tcl status-pair regression tests; worker-scoped ownership, native evidence separate.

Raw delete_DboState in the earlier candidate failed real DLL validation. These
tests forbid reintroducing it. Owned-worker exit, not this mock, proves OS cleanup.
"""
import os
from pathlib import Path
import subprocess,tempfile,unittest

HARNESS=r'''
source [lindex $argv 0]
set scenario [lindex $argv 1]
set counter 0;set deleted 0
proc DboState {} {
    set id "state[incr ::counter]"
    set ::codes($id) 0
    interp alias {} $id {} status $id
    return $id
}
proc status {id method} {
    if {$method eq "Code"} {return $::codes($id)}
    if {$method eq "Failed"} {return [expr {$::codes($id)!=0}]}
    error unexpected_status_method
}
proc delete_DboState {id} {incr ::deleted;error raw_delete_not_allowed_in_this_reader}
proc pin {method status} {
    if {$method ne "GetNet"} {error unexpected_pin_method}
    switch $::scenario {
        absent {set ::codes($status) 1021;return NULL}
        clean_absent {return NULL}
        wrong_code {set ::codes($status) 777;return NULL}
        bad_pointer_status {set ::codes($status) 1021;return NET}
        thrown {error native_thrown}
        default {return NET}
    }
}
proc DboPortInst_sGetNetName {pin status} {
    if {$::scenario eq "bad_name"} {set ::codes($status) 1021}
    return EXPECTED_NET
}
proc DboTclHelper_sGetConstCharPtr {value} {return $value}
set rc [catch {cmcp::pin_net pin} result]
if {$scenario in {absent clean_absent}} {
    if {$rc || $result ne [list false ""] || $counter!=1} {error invalid_absent_result}
} elseif {$scenario eq "present"} {
    if {$rc || $result ne [list true EXPECTED_NET] || $counter!=2} {error invalid_present_result}
} else {
    if {!$rc || $counter<1 || $counter>2 || $deleted!=0} {error failure_was_swallowed_or_unbounded_state_allocation}
}
if {$deleted!=0} {error unsafe_raw_deletion_used}
puts PASS
'''

@unittest.skipUnless(os.environ.get('CADENCE_TEST_TCLSH'),'Explicit Tcl runtime required')
class PinNetStatusTests(unittest.TestCase):
    def check_case(self,*scenarios):
        helper=Path(__file__).resolve().parents[1]/'src/cadence_mcp/adapters/dbo_pin_net.tcl'
        with tempfile.TemporaryDirectory() as temp:
            script=Path(temp)/'status.tcl';script.write_text(HARNESS,encoding='utf-8')
            for scenario in scenarios:
                result=subprocess.run([os.environ['CADENCE_TEST_TCLSH'],str(script),str(helper),scenario],
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stdout.strip(),'PASS')
    def test_absent_binding_and_clean_null(self):self.check_case('absent','clean_absent')
    def test_nonnull_error_and_unknown_null_error_are_not_swallowed(self):self.check_case('bad_pointer_status','wrong_code')
    def test_name_failure_stays_failure(self):self.check_case('bad_name')
    def test_present_name_uses_fresh_status(self):self.check_case('present')
    def test_native_exception_is_not_swallowed(self):self.check_case('thrown')
