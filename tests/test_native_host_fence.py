import json,tempfile,unittest
from pathlib import Path
from cadence_mcp.core import CadenceError
from cadence_mcp.native_host_fence import claim,ensure_idle,fence_path,read_fence,release

class NativeHostFenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.binding=Path(self.tmp.name)/'binding.json';self.binding.write_text('{}')
  self.owner={'kind':'native_netlist_v1','jobId':'a'*32,'pid':100,'instanceId':'instance',
              'jobDirectory':str(Path(self.tmp.name)/'job'),'bindingSha256':'b'*64}

 def test_pending_native_call_blocks_second_dispatch_and_metadata_write(self):
  claim(self.binding,self.owner);before=fence_path(self.binding).read_bytes()
  for action in [lambda:ensure_idle(self.binding),lambda:claim(self.binding,{**self.owner,'jobId':'c'*32})]:
   with self.assertRaises(CadenceError) as caught:action()
   self.assertEqual(caught.exception.code,'bridge_busy')
  self.assertEqual(fence_path(self.binding).read_bytes(),before)

 def test_only_exact_owner_can_release(self):
  claim(self.binding,self.owner)
  for field,value in [('jobId','c'*32),('pid',101),('instanceId','replacement'),('bindingSha256','d'*64)]:
   self.assertFalse(release(self.binding,{**self.owner,field:value}))
   self.assertEqual(read_fence(self.binding),self.owner)
  self.assertTrue(release(self.binding,self.owner));ensure_idle(self.binding)
  self.assertFalse(release(self.binding,self.owner))

 def test_truncated_or_unknown_fence_is_preserved_and_blocks_writes(self):
  path=fence_path(self.binding)
  for text in ['{',json.dumps({**self.owner,'unknown':1}),json.dumps({**self.owner,'pid':True})]:
   with self.subTest(text=text):
    path.write_text(text)
    with self.assertRaises(CadenceError):read_fence(self.binding)
    with self.assertRaises(CadenceError):release(self.binding,self.owner)
    with self.assertRaises(CadenceError):ensure_idle(self.binding)
    self.assertEqual(path.read_text(),text)

 def test_empty_host_has_no_fence(self):
  self.assertIsNone(read_fence(self.binding));ensure_idle(self.binding)

if __name__=='__main__':unittest.main()
