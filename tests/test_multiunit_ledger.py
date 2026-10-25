import tempfile,unittest
from pathlib import Path
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture_multiunit_place import CaptureMultiunitPlacements
from cadence_mcp.isolated_jobs import IsolatedJobs

class SmallJobs(IsolatedJobs):
 kind='small_test'
 def preview(self,payload):return {}

class MultiunitLedgerTests(unittest.TestCase):
 def test_group_record_can_reopen_large_geometry_without_widening_other_jobs(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);install=root/'install';install.mkdir();(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').write_bytes(b'not executed: ledger-only fixture');cfg=Config(install,root/'work',(root,));writer=CaptureMultiunitPlacements(cfg,None,None)
   payload={k:'' for k in ('reference','value','schematicName','pageName','packageName','cacheName','sourceFingerprint','libraryFingerprint')};payload['units']=[];payload['oldPageGeometry']=[{'nativeId':i,'reference':'R'+str(i),'pinNames':['X'*500]*4} for i in range(40)]
   plan=writer.create_plan(payload);directory,path,row=writer._load(plan['planId']);self.assertGreater(path.stat().st_size,65536);self.assertEqual(row['plan']['payload'],payload)
   small=SmallJobs(cfg);old=small.create_plan(payload)
   with self.assertRaises(CadenceError) as got:small._load(old['planId'])
   self.assertEqual(got.exception.code,'invalid_plan')

if __name__=='__main__':unittest.main()

