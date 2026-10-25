import copy,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import CadenceError,Config
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.pspice_dat import PSpiceDat,decode_headers

def digital():
 return {'Number':0,'AnalysisName':'Transient Analysis','PrimaryParamName':'Time','ComplexFlag':1,'DataType':1,
         'NumberofAnalogRows':0,'NumberofAnalogColumns':0,'NumberofDigitalRows':7090,'NumberofDigitalColumns':2,
         'Trace Names':{'Analog Names':[],'Digital Names':[{'INIT':['U4:INIT','INIT']},'CLK']}}
def document(row):return {'blockCount':1,'headerJSON':json.dumps([row])}

class DigitalMetadataTests(unittest.TestCase):
 def test_pure_digital_counts_aliases_and_no_physical_unit_claim(self):
  blocks,traces=decode_headers(document(digital()));block=blocks[0]
  self.assertEqual(block['rowCount'],7090);self.assertEqual(block['digitalTraceCount'],2)
  self.assertTrue(block['digitalMetadataComplete']);self.assertFalse(block['digitalReadSupported']);self.assertFalse(block['analogReadSupported'])
  self.assertEqual(traces[0][0]['aliases'],['U4:INIT']);self.assertEqual(traces[0][0]['signalType'],'digital')
  self.assertIsNone(traces[0][0]['unit']);self.assertFalse(traces[0][0]['sampleReadSupported'])
 def test_mixed_keeps_separate_row_counts_and_axis(self):
  row=digital();row.update(DataType=2,NumberofAnalogRows=3,NumberofAnalogColumns=2)
  row['Trace Names']['Analog Names']=['Time','V(OUT)']
  blocks,traces=decode_headers(document(row));block=blocks[0]
  self.assertEqual((block['analogRowCount'],block['digitalRowCount'],block['traceCount']),(3,7090,4))
  self.assertEqual([t['signalType'] for t in traces[0]],['analog','analog','digital','digital'])
  self.assertTrue(block['analogReadSupported'])
 def test_legacy_mixed_incomplete_digital_metadata_is_explicit(self):
  row=digital();row.update(DataType=2,NumberofAnalogRows=1,NumberofAnalogColumns=1)
  del row['NumberofDigitalRows'];del row['NumberofDigitalColumns'];row['Trace Names']={'Analog Names':['Time']}
  blocks,_=decode_headers(document(row));self.assertFalse(blocks[0]['digitalMetadataComplete']);self.assertIsNone(blocks[0]['digitalRowCount'])
 def test_bad_counts_missing_fields_and_analog_misclassification_rejected(self):
  for key,value in [('NumberofDigitalRows',True),('NumberofDigitalRows',100001),('NumberofDigitalColumns',3),('NumberofAnalogRows',1),('DataType',0)]:
   row=digital();row[key]=value
   with self.subTest(key=key,value=value),self.assertRaises(CadenceError):decode_headers(document(row))
  for key in ('NumberofDigitalRows','NumberofDigitalColumns'):
   row=digital();del row[key]
   with self.assertRaises(CadenceError):decode_headers(document(row))
 def test_cross_domain_alias_collision_and_invalid_names_refused(self):
  row=digital();row.update(DataType=2,NumberofAnalogRows=1,NumberofAnalogColumns=1)
  row['Trace Names']['Analog Names']=[{'Time':['U4:INIT']}]
  with self.assertRaises(CadenceError):decode_headers(document(row))
  for bad in ['',{'A':['']},{'A':['x\nline']},'x'*513]:
   row=digital();row['Trace Names']['Digital Names'][0]=bad
   with self.subTest(bad=bad),self.assertRaises(CadenceError):decode_headers(document(row))
 def test_no_fake_time_trace_required_when_analog_columns_zero(self):
  row=digital();blocks,traces=decode_headers(document(row))
  self.assertEqual(blocks[0]['axis'],'Time');self.assertNotIn('Time',[t['name'] for t in traces[0]])
 def test_digital_catalog_available_but_sample_worker_never_called(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();source=root/'source.dat';source.write_bytes(b'owned digital fixture')
   service=PSpiceDat(Config(install,root/'work',(root,)))
   with patch.object(service,'_worker',return_value=document(digital())) as worker:
    ident=service.open(str(source))['datId'];self.assertEqual(service.query(ident,'trace',0)['total'],2)
    with self.assertRaises(CadenceError) as caught:service.samples(ident,0,'INIT')
    self.assertEqual(caught.exception.code,'capability_unavailable');self.assertEqual(worker.call_count,1)
 def test_failed_native_close_is_not_retried(self):
  tcl=os.environ.get('CADENCE_TEST_TCLSH')
  if not tcl or not Path(tcl).is_file():self.skipTest('Configured Tcl unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);calls=root/'calls.txt';output=root/'output.json';script=root/'harness.tcl'
   text='''set calls {%s}
rename load actualLoad
proc load {args} {return {}}
proc orPIOObject {name} {interp alias {} $name {} fakeReader}
proc fakeReader {method args} {
 global calls
 switch -- $method {
  loadFile {return 1}
  getNumberofBlocks {return 1}
  getJSON {return {[]}}
  close {set f [open $calls a];puts $f close;close $f;return 0}
  default {error unexpected_method}
 }
}
set argc 7
set argv [list INSTALL INPUT {%s} headers 0 {} {%s}]
source {%s}
'''%(calls.as_posix(),output.as_posix(),(ADAPTERS/'json.tcl').as_posix(),(ADAPTERS/'inspect_dat.tcl').as_posix())
   script.write_text(text,encoding='utf-8');child=subprocess.run([tcl,str(script)],cwd=root,capture_output=True,timeout=10)
   self.assertEqual(child.returncode,1);self.assertEqual(calls.read_text().splitlines(),['close'])
   self.assertEqual(json.loads(output.read_text())['phase'],'close_reader')

if __name__=='__main__':unittest.main()
