import copy,unittest
from cadence_mcp.capture_net_symbol_edit import symbol_changes,symbol_name_conflicts,symbol_pose_changes,expected_symbol_metadata
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

 def test_terminal_pose_extends_only_selected_endpoint_without_mutating_snapshot(self):
  before=copy.deepcopy(self.objects)
  changed,pose=symbol_pose_changes(self.objects,self.target,self.objects[1],[0,20],0,0,[10,30],[[50,30]])
  self.assertEqual(self.objects,before);self.assertEqual(changed[1]['attributes']['points'],[[10,30],[50,30]])
  self.assertEqual(changed[0]['attributes']['hotSpot'],[10,30]);self.assertEqual(pose['wireEndIndex'],0)

 def test_anchored_rotation_keeps_lead_and_allows_existing_endpoint_pin(self):
  changed,_=symbol_pose_changes(self.objects,self.target,self.objects[1],[20,10],1,0,[20,30],[[20,30]])
  self.assertEqual(changed[1],self.objects[1]);self.assertEqual(changed[0]['attributes']['rotationCode'],1)

 def test_moving_terminal_rejects_other_pin_wire_and_alias_dependencies(self):
  for extras,pins in [([],[[20,30]]),([{'objectId':'branch','pageId':'page','kind':'wire','attributes':{'points':[[20,30],[20,70]]}}],[]),([{'objectId':'a','pageId':'page','kind':'alias','attributes':{'wireId':'wire','location':[35,30]}}],[])]:
   with self.subTest(extras=extras,pins=pins),self.assertRaises(CadenceError):
    symbol_pose_changes([*self.objects,*extras],self.target,self.objects[1],[30,20],0,0,[40,30],pins)

 def test_pose_rejects_diagonal_collapsed_interior_and_boolean_rotation(self):
  for location,rotation,hotspot in [([0,20],0,[10,40]),([40,20],0,[50,30]),([0,20],True,[10,30])]:
   with self.subTest(hotspot=hotspot),self.assertRaises(CadenceError):symbol_pose_changes(self.objects,self.target,self.objects[1],location,rotation,0,hotspot,[])
  wire=copy.deepcopy(self.objects[1]);wire['attributes']['points']=[[10,30],[50,30]]
  with self.assertRaises(CadenceError):symbol_pose_changes(self.objects,self.target,wire,[0,20],0,0,[10,30],[])

 def test_recreation_freezes_only_declared_coordinates_and_explicit_cache_rebind(self):
  metadata={'effective':[{'name':'Location X-Coordinate','value':'10'},{'name':'Location Y-Coordinate','value':'20'},{'name':'Source Library','value':'C:/fixture/old.dsn'},{'name':'NOTE','value':'00123 Ω'}],'user':[{'name':'NOTE','value':'00123 Ω'}],'display':[{'name':'NOTE','font':[700],'fontDefault':False}]};before=copy.deepcopy(metadata)
  expected=expected_symbol_metadata(metadata,[30,40],True)
  self.assertEqual(metadata,before);self.assertEqual(expected['user'],metadata['user']);self.assertEqual(expected['display'],metadata['display'])
  self.assertEqual([p['value'] for p in expected['effective']],['30','40','__OWNED_OUTPUT_CACHE__','00123 Ω'])
  metadata['effective'][2]['value']='C:/external/source.olb'
  with self.assertRaises(CadenceError):expected_symbol_metadata(metadata,[30,40],True)
  self.assertEqual(expected_symbol_metadata(metadata,[30,40],False)['effective'][2]['value'],'C:/external/source.olb')
