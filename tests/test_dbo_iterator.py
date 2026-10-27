import os,subprocess,tempfile,unittest
from pathlib import Path
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.gui_loader import tcl_string
TCL=os.environ.get('CADENCE_TEST_TCLSH')

@unittest.skipUnless(TCL and Path(TCL).is_file(),'Native Tcl executable not configured')
class IteratorTerminationTests(unittest.TestCase):
 def run_case(self,result,failed,code,method='NextPort'):
  script='''set created 0;set invoked 0
proc DboState {} {incr ::created;set name "st$::created";interp alias {} $name {} status;return $name}
proc status {method} {switch -- $method {Failed {return FAILED} Code {return CODE} default {error unexpected_state_method}}}
proc iterator {method state} {incr ::invoked;return RESULT}
source HELPER
set caught [catch {::cmcp::next_object iterator METHOD} value]
puts [list $caught $value $::created $::invoked]
'''.replace('FAILED',str(int(failed))).replace('CODE',str(code)).replace('RESULT',tcl_string(result)).replace('HELPER',tcl_string((ADAPTERS/'dbo_iterator.tcl').as_posix())).replace('METHOD',tcl_string(method))
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'check.tcl';path.write_text(script,encoding='utf-8');child=subprocess.run([TCL,str(path)],capture_output=True,text=True,timeout=10)
  self.assertEqual(child.returncode,0,child.stderr);return child.stdout.strip().split()
 def test_valid_object_uses_fresh_state(self):self.assertEqual(self.run_case('object-1',False,0),['0','object-1','1','1'])
 def test_null_normal_end_is_accepted(self):self.assertEqual(self.run_case('NULL',True,1022),['0','NULL','1','1'])
 def test_null_success_is_accepted(self):self.assertEqual(self.run_case('NULL',False,0),['0','NULL','1','1'])
 def test_same_status_on_nonnull_object_is_not_masked(self):self.assertEqual(self.run_case('object-1',True,1022)[:2],['1','iterator_failed_1022'])
 def test_other_null_errors_are_not_masked(self):self.assertEqual(self.run_case('NULL',True,3969)[:2],['1','iterator_failed_3969'])
 def test_unknown_method_never_reaches_native_iterator(self):self.assertEqual(self.run_case('NULL',True,1022,'Delete'),['1','unsupported_iterator_method','0','0'])
 def test_empty_result_is_not_silently_end(self):self.assertEqual(self.run_case('',False,0)[:2],['1','invalid_iterator_result'])

if __name__=='__main__':unittest.main()
