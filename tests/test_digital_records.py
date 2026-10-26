import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import CadenceError,Config
from cadence_mcp.pspice_dat import PSpiceDat,decode_headers
from cadence_mcp.pspice_digital import decode_digital_records
from test_dat_digital_metadata import digital,document

class DigitalRecordsTests(unittest.TestCase):
 def setUp(self):
  self.block=decode_headers(document(digital()))[0][0]
  self.raw={'block':0,'trace':'INIT','blockDigitalRows':7090,'nativeDigitalData':"INIT'4,0,63,1,-976551600,0.000002055,63,0,419,0.000002095,63,1,-932216256,0.001,63,1,419"}
 def test_compressed_count_signed_opaque_and_exact_time(self):
  rows=decode_digital_records(self.raw,self.block,'INIT')
  self.assertEqual(len(rows),4);self.assertEqual([x['state'] for x in rows],list('1011'))
  self.assertEqual(rows[-1]['time'],.001);self.assertEqual(set(rows[0]),{'index','time','state','stateCode','strengthCode'})
 def test_six_states_and_opaque_invariance(self):
  raw=dict(self.raw,nativeDigitalData="INIT'6,"+','.join(f'{i},0,{i},0' for i in range(6)))
  rows=decode_digital_records(raw,self.block,'INIT');self.assertEqual(''.join(r['state'] for r in rows),'01XRFZ')
  raw['nativeDigitalData']="INIT'6,"+','.join(f'{i},0,{i},4294967295' for i in range(6))
  self.assertEqual(rows,decode_digital_records(raw,self.block,'INIT'))
 def test_flags_never_masked_or_partially_returned(self):
  raw=dict(self.raw,nativeDigitalData="INIT'2,0,25,0,0,1,0,26,0")
  with self.assertRaises(CadenceError) as c:decode_digital_records(raw,self.block,'INIT')
  self.assertEqual(c.exception.code,'unsupported_digital_state_flags')
 def test_bad_frames_bounds_and_nonfinite(self):
  for text in ["INIT'1,0,64,0,0","INIT'1,0,-1,0,0","INIT'1,NaN,0,0,0","INIT'1,1e999,0,0,0","INIT'1,-1,0,0,0","INIT'2,1,0,0,0,0,0,0,0","INIT'1,0,0,0,4294967296","INIT'1,0,0,-1,0","INIT'1,0,0,0","INIT'7091", "OTHER'0,", "INIT'01,0,0,0,0,extra"]:
   with self.subTest(text=text),self.assertRaises(CadenceError):decode_digital_records(dict(self.raw,nativeDigitalData=text),self.block,'INIT')
 def test_receipt_identity_checked(self):
  for key,value in [('block',True),('block',1),('trace','CLK'),('blockDigitalRows',4),('extra',1)]:
   with self.subTest(key=key),self.assertRaises(CadenceError):decode_digital_records(dict(self.raw,**{key:value}),self.block,'INIT')
 def test_unsupported_metadata_not_advertised(self):
  for update in [dict(PrimaryParamName='Frequency'),dict(AnalysisName='AC Analysis'),dict(NumberofDigitalRows=0)]:
   row=digital();row.update(update);blocks,traces=decode_headers(document(row))
   self.assertFalse(blocks[0]['digitalReadSupported']);self.assertFalse(traces[0][0]['sampleReadSupported'])
 def service(self,root):
  install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'source.dat';source.write_bytes(b'owned fixture')
  service=PSpiceDat(Config(install,root/'work',(root,)))
  with patch.object(service,'_worker',return_value=document(digital())):ident=service.open(str(source))['datId']
  return service,ident
 def test_alias_paging_uses_per_trace_count(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,ident=self.service(Path(tmp))
   with patch.object(service,'_worker',return_value=self.raw) as worker:
    result=service.digital_samples(ident,0,'U4:INIT',1,2)
    self.assertEqual(result['total'],4);self.assertEqual(result['nextOffset'],3);self.assertEqual(result['trace'],'INIT')
    self.assertEqual(worker.call_args.args[1:],('digital_trace',0,'INIT'));self.assertFalse(result['nativeOpaqueTailReturned'])
    with self.assertRaises(CadenceError) as caught:service.digital_samples(ident,0,'INIT',5)
    self.assertEqual(caught.exception.code,'invalid_query')
 def test_unsafe_names_and_queries_never_reach_worker(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,ident=self.service(Path(tmp))
   with patch.object(service,'_worker') as worker:
    for name in ['Time','MISSING','V(OUT)']:
     with self.subTest(name=name),self.assertRaises(CadenceError) as caught:service.digital_samples(ident,0,name)
     self.assertEqual(caught.exception.code,'trace_not_found')
    for block,offset,limit in [(True,0,1),(1,0,1),(0,-1,1),(0,0,0),(0,0,True)]:
     with self.assertRaises(CadenceError):service.digital_samples(ident,block,'INIT',offset,limit)
    worker.assert_not_called()
 def test_snapshot_change_and_closed_session_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   service,ident=self.service(Path(tmp))
   with patch.object(service,'_worker') as worker:
    target=service.sessions[ident]['directory']/'imported.dat';target.write_bytes(b'tampered')
    with self.assertRaises(CadenceError) as c:service.digital_samples(ident,0,'INIT')
    self.assertEqual(c.exception.code,'target_changed');worker.assert_not_called()
    service.sessions.pop(ident)
    with self.assertRaises(CadenceError) as c:service.digital_samples(ident,0,'INIT')
    self.assertEqual(c.exception.code,'session_lost')
if __name__=='__main__':unittest.main()

