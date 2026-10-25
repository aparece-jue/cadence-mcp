import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.pspice_dat import PSpiceDat

class MixedAnalogTests(unittest.TestCase):
 def test_mixed_analog_values_and_different_logic_row_counts(self):
  self.exercise(False)
 def test_logic_never_reaches_numeric_native_reader_or_axis_measurement(self):
  self.exercise(True)
 def exercise(self,digital_only):
  row={'Number':0,'AnalysisName':'Transient Analysis','PrimaryParamName':'Time','ComplexFlag':1,'DataType':2,
       'NumberofAnalogRows':3,'NumberofAnalogColumns':2,'NumberofDigitalRows':5,'NumberofDigitalColumns':1,
       'Trace Names':{'Analog Names':['Time','V(N)'],'Digital Names':[{'DIN':['DATA']} ]}}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();source=root/'mixed.dat';source.write_bytes(b'owned mixed fixture')
   data=PSpiceDat(Config(install,root/'work',(root,)))
   def worker(directory,mode,block=0,trace=''):
    if mode=='headers':return {'blockCount':1,'headerJSON':json.dumps([row])}
    self.assertIn(trace,('Time','V(N)'))
    return {'block':0,'trace':trace,'rows':3,'valuesCSV':'0,1,2' if trace=='Time' else '1,1,1'}
   with patch.object(data,'_worker',side_effect=worker) as native:
    ident=data.open(str(source))['datId']
    if digital_only:
     for call in (lambda:data.samples(ident,0,'DIN'),lambda:data.samples(ident,0,'DATA'),lambda:data.measure(ident,0,'DIN')):
      with self.assertRaises(CadenceError) as caught:call()
      self.assertEqual(caught.exception.code,'capability_unavailable')
     self.assertEqual(native.call_count,1)
    else:
     result=data.samples(ident,0,'V(N)',1,2);self.assertEqual([v['real'] for v in result['items']],[1,1]);self.assertEqual(result['unit'],'V')
     measured=data.measure(ident,0,'V(N)');self.assertEqual(measured['sampleMean'],1)
     traces=data.query(ident,'trace',0)['items'];self.assertEqual([t['rowCount'] for t in traces],[3,3,5])

if __name__=='__main__':unittest.main()
