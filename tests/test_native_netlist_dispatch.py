import os,subprocess,tempfile,unittest
from pathlib import Path
from cadence_mcp.capture_pspice_netlist import _write_dispatch_files
from cadence_mcp.gui_loader import tcl_string

class NativeNetlistDispatchTests(unittest.TestCase):
 def test_command_file_has_one_source_command_and_complete_payload(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);code='if {1} {\n set result accepted\n}\n'
   wrapper=_write_dispatch_files(root,code)
   self.assertEqual(wrapper.read_text(), 'source '+tcl_string((root/'payload.tcl').as_posix())+'\n')
   self.assertEqual(len(wrapper.read_text().splitlines()),1)
   self.assertEqual((root/'payload.tcl').read_text(),code)
   with self.assertRaises(FileExistsError):_write_dispatch_files(root,'overwritten')
   self.assertEqual((root/'payload.tcl').read_text(),code)

 def test_replayed_command_sources_multiline_refusal_handler_with_literal_paths(self):
  tcl=os.environ.get('CADENCE_TEST_TCLSH')
  if not tcl or not Path(tcl).is_file():self.skipTest('Configured Tcl unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'space [literal] $value';root.mkdir();output=root/'refused.txt'
   code='set caught [catch {error bridge_busy} message]\n'
   code+='if {$caught && $message in {bridge_busy wrong_active_design output_exists}} {\n'
   code+='set f [open '+tcl_string(output.as_posix())+' {WRONLY CREAT EXCL}]\nputs $f $message\nclose $f\n}\n'
   wrapper=_write_dispatch_files(root,code)
   # Reproduce Capture command-file line replay; do not have tclsh parse payload directly.
   runner=root/'replay.tcl'
   runner.write_text('set replayChannel [open '+tcl_string(wrapper.as_posix())+' r]\nwhile {[gets $replayChannel line]>=0} {uplevel #0 $line}\nclose $replayChannel\n',encoding='utf-8')
   result=subprocess.run([tcl,str(runner)],capture_output=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
   self.assertEqual(output.read_text().strip(),'bridge_busy')

if __name__=='__main__':unittest.main()
