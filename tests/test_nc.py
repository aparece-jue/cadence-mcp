import copy,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture_nc import nc_expectation,CaptureNcEdits
from cadence_mcp.capture_wire import connection_digest
class NcTests(unittest.TestCase):
 def fixture(self):
  data={'schematic':[{'objectId':'s','name':'S'}],'page':[{'objectId':'p','schematicId':'s','name':'P'}],'part':[{'objectId':'a','pageId':'p','schematicId':'s','reference':'R1'}],'pin':[{'objectId':'a/1','partId':'a','pageId':'p','schematicId':'s','reference':'R1','number':'1','name':'A','connected':False,'net':''}]}
  wire={'kind':'wire','pageId':'p','attributes':{'points':[[0,0],[10,0]],'net':'N'}}
  return data,wire
 def marker(self,part='a',number='1',spot=None):return {'kind':'nc','pageId':'p','attributes':{'partId':part,'pinId':part+'/'+number,'reference':'R1' if part=='a' else 'R2','number':number,'hotSpot':spot or [20,0]}}
 def test_add_binds_hotspot_and_preserves_every_other_connection_without_mutation(self):
  data,wire=self.fixture();objs=[wire,self.marker('other')];before=copy.deepcopy(objs)
  old,digest=nc_expectation(data,objs,data['pin'][0],[20,0],True)
  self.assertFalse(old);self.assertEqual(digest,connection_digest(data,objs+[self.marker()]));self.assertEqual(objs,before)
  self.assertNotEqual(digest,connection_digest(data,objs+[self.marker(spot=[21,0])]))
 def test_remove_only_selected_marker_and_keep_other_pin_flags(self):
  data,wire=self.fixture();selected=self.marker();other=self.marker('other');objs=[wire,selected,other];before=copy.deepcopy(objs)
  old,digest=nc_expectation(data,objs,data['pin'][0],[20,0],False)
  self.assertTrue(old);self.assertEqual(digest,connection_digest(data,[wire,other]));self.assertEqual(objs,before)
 def test_noop_and_duplicate_target_markers_are_not_silently_accepted(self):
  data,wire=self.fixture()
  for objs,enabled in [([wire],False),([wire,self.marker()],True),([wire,self.marker(),self.marker()],False)]:
   with self.assertRaises(CadenceError):nc_expectation(data,objs,data['pin'][0],[20,0],enabled)
 def test_bad_type_connected_and_package_scope_rejected_before_plan_creation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();data,_=self.fixture();cap=SimpleNamespace(lock=threading.RLock(),_session=lambda sid:{'data':data});writer=CaptureNcEdits(Config(install,root/'work',(root,)),cap)
   for value in (1,0,'true',None):
    with self.assertRaises(CadenceError):writer.plan('s','a/1',value)
   data['pin'][0]['connected']=True
   with self.assertRaises(CadenceError):writer.plan('s','a/1',True)
   data['pin'][0]['connected']=False
   for kind,size,external in [('placed',2,False),('drawn',0,False),('placed',1,True)]:
    with patch('cadence_mcp.capture_nc.read_units',return_value={'a':{'kind':kind,'packageSize':size,'isExternalDesignPart':external}}):
     with self.assertRaises(CadenceError):writer.plan('s','a/1',True)
   self.assertFalse(list(writer.root.glob('plan-*')))
