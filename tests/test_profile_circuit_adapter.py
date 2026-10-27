import json,os,subprocess,tempfile,unittest
from pathlib import Path
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.gui_loader import tcl_string

class ProfileCircuitAdapterTests(unittest.TestCase):
 def run_case(self,mode):
  tcl=os.environ.get('CADENCE_TEST_TCLSH')
  if not tcl or not Path(tcl).is_file():self.skipTest('Configured Tcl unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);project=root/'project.opj';profile=root/'profile.sim';ini=root/'private.ini'
   for p in [project,profile,ini]:p.write_text('fixture')
   circuit=root/'output.cir';output=root/'receipt.json';summary=root/'summary.json'
   if mode=='preexisting':circuit.write_text('preserve')
   args=[root,project,profile,ini,circuit,output,'a'*32]
   code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'profile_circuit_job.tcl').as_posix())+'\n'
   code+='set mode '+tcl_string(mode)+'\nset expected '+tcl_string(circuit.as_posix())+'\nset constructed 0;set deleted 0\n'
   code+='''rename load native_load
proc load {args} {}
proc new_CorSimSrvr {args} {incr ::constructed;return object}
proc CorSimSrvr_setIniFile {args} {}
proc delete_CorSimSrvr {args} {incr ::deleted;if {$::mode eq "cleanup"} {error cleanup_failed}}
proc object {method args} {
 if {$method eq "updateCirFileI"} {
  upvar 1 [lindex $args 0] actual
  set actual $::expected
  if {$::mode eq "wrongPath"} {append actual .wrong}
  set f [open $actual w];puts $f "* own circuit";close $f
  if {$::mode eq "nativeFailure"} {return 1}
 }
 return 0
}
'''
   code+='set caught [catch {::cmcpProfileCircuit::run '+' '.join(tcl_string(x.as_posix() if isinstance(x,Path) else x) for x in args)+'} message]\n'
   code+='set f [open '+tcl_string(summary.as_posix())+' w];puts $f [cmcp::obj constructed $constructed deleted $deleted caught $caught message [cmcp::q $message]];close $f\n'
   script=root/'run.tcl';script.write_text(code)
   child=subprocess.run([tcl,str(script)],capture_output=True,timeout=10)
   self.assertEqual(child.returncode,0,child.stderr.decode(errors='replace'))
   return json.loads(summary.read_text()),json.loads(output.read_text()) if output.exists() else None,circuit.read_text() if circuit.exists() else None

 def test_preexisting_circuit_refuses_before_constructing_native_object(self):
  summary,receipt,circuit=self.run_case('preexisting')
  self.assertEqual(summary['constructed'],0);self.assertEqual(summary['message'],'preexisting_profile_output')
  self.assertIsNone(receipt);self.assertEqual(circuit,'preserve')

 def test_native_failure_and_unexpected_circuit_path_are_not_success(self):
  for mode,error in [('nativeFailure','native_profile_failure'),('wrongPath','unexpected_circuit_path')]:
   with self.subTest(mode=mode):
    summary,receipt,_=self.run_case(mode)
    self.assertEqual(summary['deleted'],1);self.assertFalse(receipt['invocationReturned'])
    self.assertEqual(receipt['error'],error);self.assertEqual(receipt['phase'],'update_cir')

 def test_cleanup_failure_does_not_become_success(self):
  summary,receipt,_=self.run_case('cleanup')
  self.assertEqual(summary['deleted'],1);self.assertFalse(receipt['invocationReturned']);self.assertEqual(receipt['phase'],'cleanup')

if __name__=='__main__':unittest.main()
