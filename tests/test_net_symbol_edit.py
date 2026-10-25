import copy,unittest
from cadence_mcp.capture_net_symbol_edit import symbol_changes,symbol_name_conflicts
from cadence_mcp.core import CadenceError

class NetSymbolEditTests(unittest.TestCase):
 def setUp(self):
  self.target={'objectId':'symbol','kind':'global','pageId':'page','attributes':{'name':'OLD','sourceSymbol':'VCC','location':[10,20],'hotSpot':[20,30],'rotationCode':0,'mirrorCode':0,'isBus':False}}
  self.objects=[self.target,{'objectId':'wire','kind':'wire','pageId':'page','attributes':{'points':[[20,30],[50,30]],'net':'OLD'}}]
 def test_rename_preserves_pose_wire_and_original_snapshot(self):
  original=copy.deepcopy(self.objects);new=symbol_changes(self.objects,self.target,'set_name','NEW')
  self.assertEqual(self.objects,original);self.assertEqual(new[1],original[1]);self.assertEqual(new[0]['attributes'],{**original[0]['attributes'],'name':'NEW'})
 def test_unaccepted_pose_bus_and_inconsistent_delete_refused(self):
  for operation,name in [('set_pose',None),('delete','NEW'),('set_name','OLD'),('set_name','DATA[7..0]'),('set_name','A\nB')]:
   with self.assertRaises(CadenceError):symbol_changes(self.objects,self.target,operation,name)
  bus=copy.deepcopy(self.target);bus['attributes']['isBus']=True
  with self.assertRaises(CadenceError):symbol_changes([bus],bus,'delete',None)
 def test_delete_removes_only_selected_instance(self):
  other=copy.deepcopy(self.target);other['objectId']='other';objects=[*self.objects,other]
  result=symbol_changes(objects,self.target,'delete',None)
  self.assertEqual(result,[self.objects[1],other]);self.assertEqual(len(objects),3)

 def test_case_insensitive_conflict_covers_known_connection_kinds(self):
  for kind,key in [('wire','net'),('alias','name'),('global','name'),('offpage','name'),('port','name')]:
   other={'objectId':'other','kind':kind,'attributes':{key:'MCP_MIDDLE'}}
   self.assertTrue(symbol_name_conflicts([*self.objects,other],'symbol','wire','mcp_middle'))
 def test_own_wire_and_symbol_do_not_create_false_name_conflict(self):
  self.assertFalse(symbol_name_conflicts(self.objects,'symbol','wire','old'))
  self.assertFalse(symbol_name_conflicts(self.objects,'symbol','wire','FRESH'))
