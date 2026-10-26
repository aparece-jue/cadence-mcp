import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.capture_pspice_receipt import decode_receipt

class NativeReceiptTests(unittest.TestCase):
 def good(self):return {'jobId':'a'*32,'pid':5256,'invocationReturned':True,'phase':'returned','nativeReturn':'1','error':'','logs':[{'category':c,'readable':True,'lines':[]} for c in ['errors','warnings','session','netlist']]}
 def test_exact_receipt_accepts_warning_and_denies_forwarder_proof(self):
  raw=self.good();raw['logs'][1]['lines']=['WARNING native warning'];r=decode_receipt(raw,'a'*32,5256);self.assertEqual(r['warningCount'],1);self.assertFalse(r['forwarderExitIsCompletionProof'])
 def test_pid_job_identity_extra_and_boolean_types_refused(self):
  for key,value in [('pid',True),('pid',1),('jobId','b'*32),('invocationReturned',1),('extra',1)]:
   with self.subTest(key=key),self.assertRaises(CadenceError) as c:decode_receipt(dict(self.good(),**{key:value}),'a'*32,5256)
   self.assertEqual(c.exception.code,'invalid_native_receipt')
 def test_invalid_expected_identity_cannot_certify_receipt(self):
  for nonce,pid in [('bad',5256),('a'*32,True),('a'*32,0)]:
   with self.assertRaises(CadenceError):decode_receipt(self.good(),nonce,pid)
 def test_native_failure_and_no_return_never_certified(self):
  for key,value in [('invocationReturned',False),('phase','generate'),('nativeReturn','0'),('nativeReturn','true'),('error','native_failure')]:
   with self.subTest(key=key),self.assertRaises(CadenceError) as c:decode_receipt(dict(self.good(),**{key:value}),'a'*32,5256)
   self.assertEqual(c.exception.code,'native_netlist_failed')
 def test_unreadable_or_nonempty_logs_refused(self):
  raw=self.good();raw['logs'][0]['lines']=['INFO(ORNET-1165): Unable to initialize pspice explorer']
  with self.assertRaises(CadenceError) as c:decode_receipt(raw,'a'*32,5256)
  self.assertEqual(c.exception.code,'native_netlist_failed')
  for index in range(4):
   raw=self.good();raw['logs'][index]['readable']=False
   with self.assertRaises(CadenceError) as c:decode_receipt(raw,'a'*32,5256)
   self.assertEqual(c.exception.code,'native_log_unavailable')
 def test_missing_duplicate_category_oversized_and_unknown_log_fields_refused(self):
  for mode in ['missing','duplicate','wrong_bool','oversized','extra']:
   raw=self.good()
   if mode=='missing':raw['logs'].pop()
   if mode=='duplicate':raw['logs'][1]['category']='errors'
   if mode=='wrong_bool':raw['logs'][0]['readable']=1
   if mode=='oversized':raw['logs'][0]['lines']=['a'*4097]
   if mode=='extra':raw['logs'][0]['extra']=1
   with self.subTest(mode=mode),self.assertRaises(CadenceError):decode_receipt(raw,'a'*32,5256)
if __name__=='__main__':unittest.main()
