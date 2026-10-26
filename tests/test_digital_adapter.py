import json,os,subprocess,tempfile,unittest
from pathlib import Path
from cadence_mcp.environment import ADAPTERS

class DigitalAdapterGuards(unittest.TestCase):
 def run_adapter(self,trace='INIT',close_result=1):
  tcl=os.environ.get('CADENCE_TEST_TCLSH')
  if not tcl or not Path(tcl).is_file():self.skipTest('Configured Tcl unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);calls=root/'calls.txt';output=root/'result.json';script=root/'harness.tcl'
   harness='''rename load actualLoad
proc load {args} {return {}}
proc orPIOObject_getDigital {args} {return {}}
proc orPIOObject {name} {interp alias {} $name {} fakeReader}
proc fakeReader {method args} {
 global calls closeResult
 set f [open $calls a];puts $f $method;close $f
 switch -- $method {
 loadFile {return 1}
 getNumberofBlocks {return 1}
 setBlock {return 1}
 getHeaderData {switch -- [lindex $args 0] {
 DataType {return 1}
 NumberofDigitalRows {return 7090}
 NumberofDigitalColumns {return 1}
 PrimaryParamName {return Time}
 AnalysisName {return {Transient Analysis}}
 default {error bad_header}
 }}
 getDataNames {return {INIT;U4:INIT}}
 getDigital {return {INIT'1,0,63,1,-123}}
 close {return $closeResult}
 default {error unexpected_method}
 }
}
'''
   script.write_text('set calls {'+calls.as_posix()+'}\nset closeResult '+str(close_result)+'\n'+harness+'\nset argc 7\nset argv [list INSTALL INPUT {'+output.as_posix()+'} digital_trace 0 {'+trace+'} {'+(ADAPTERS/'json.tcl').as_posix()+'}]\nsource {'+(ADAPTERS/'inspect_digital_dat.tcl').as_posix()+'}\n',encoding='utf-8')
   child=subprocess.run([tcl,str(script)],cwd=root,capture_output=True,timeout=10)
   return child.returncode,json.loads(output.read_text()),calls.read_text().splitlines()
 def test_axis_and_alias_never_reach_native_digital_method(self):
  for trace in ['Time','MISSING','U4:INIT']:
   with self.subTest(trace=trace):
    rc,output,calls=self.run_adapter(trace);self.assertEqual(rc,1);self.assertEqual(output['phase'],'validate_digital_directory')
    self.assertNotIn('getDigital',calls);self.assertEqual(calls.count('close'),1)
 def test_failed_close_not_retried(self):
  rc,output,calls=self.run_adapter(close_result=0);self.assertEqual(rc,1);self.assertEqual(output['phase'],'close_reader');self.assertEqual(calls.count('close'),1)
 def test_canonical_success_private_raw_receipt(self):
  rc,output,calls=self.run_adapter();self.assertEqual(rc,0);self.assertEqual(output['blockDigitalRows'],7090);self.assertEqual(output['nativeDigitalData'],"INIT'1,0,63,1,-123");self.assertEqual(calls.count('close'),1)
if __name__=='__main__':unittest.main()
