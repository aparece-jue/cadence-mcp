import copy,tempfile,unittest
from pathlib import Path
from cadence_mcp.capture_net_symbol_create import symbol_expectation,CaptureNetSymbolCreates
from cadence_mcp.core import Config,CadenceError,sha256
class NetSymbolCreateTests(unittest.TestCase):
 def test_origin_hotspot_and_lead_are_explicit_and_inputs_preserved(self):
  objects=[{'kind':'wire','pageId':'p','attributes':{'points':[[0,0],[10,0]],'net':'OLD'}}];old=copy.deepcopy(objects)
  rows=symbol_expectation(objects,'p','global','SUPPLY','CACHE',[20,20],[30,30],0,0,[40,30]);self.assertEqual(objects,old);self.assertEqual(rows[1]['attributes']['location'],[20,20]);self.assertEqual(rows[1]['attributes']['hotSpot'],[30,30]);self.assertEqual(rows[2]['attributes']['points'],[[30,30],[40,30]])
 def test_port_bus_name_invalid_pose_and_lead_are_refused(self):
  base=['p','global','N','C',[0,0],[10,10],0,0,None]
  for index,value in [(1,'port'),(2,'DATA[7..0]'),(4,[True,0]),(6,True),(7,2),(8,[11,11]),(8,[10,10])]:
   args=copy.deepcopy(base);args[index]=value
   with self.assertRaises(CadenceError):symbol_expectation([], *args)
 def test_duplicate_instance_or_existing_lead_is_not_created_again(self):
  obj={'kind':'global','pageId':'p','attributes':{'name':'N','location':[0,0]}}
  with self.assertRaises(CadenceError):symbol_expectation([obj],'p','global','N','C',[0,0],[10,10],0,0,None)
  wire={'kind':'wire','pageId':'p','attributes':{'points':[[10,10],[20,10]],'net':'N'}}
  with self.assertRaises(CadenceError):symbol_expectation([wire],'p','global','N','C',[0,0],[10,10],0,0,[20,10])
 def test_preflight_binds_both_design_and_library_snapshots(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();cfg=Config(install,root/'work',(root,));writer=CaptureNetSymbolCreates(cfg,None,None);design=cfg.workspace_root/'design.dsn';lib=cfg.workspace_root/'library.olb';design.write_bytes(b'design');lib.write_bytes(b'library');p={'sourceDesign':str(design),'sourceFingerprint':sha256(design),'sourceLibrary':str(lib),'libraryFingerprint':sha256(lib),'cacheName':'MCP_SHORT'};writer.preflight(p)
   with self.assertRaises(CadenceError):writer.preflight({**p,'cacheName':'A'*32})
   lib.write_bytes(b'changed')
   with self.assertRaises(CadenceError):writer.preflight(p)
   lib.write_bytes(b'library');design.write_bytes(b'changed')
   with self.assertRaises(CadenceError):writer.preflight(p)
