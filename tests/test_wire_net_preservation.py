import copy,unittest
from cadence_mcp.capture_wire_edit import unrelated_wire_nets,verify_unrelated_wire_nets,CaptureWireEdits
from cadence_mcp.capture_wire import CaptureWireAdds
from cadence_mcp.core import CadenceError

class UnrelatedWireNetTests(unittest.TestCase):
 def setUp(self):
  self.data={'schematic':[{'objectId':'s','name':'ROOT'}],'page':[{'objectId':'p','schematicId':'s','name':'MAIN'}]}
  self.objects=[{'kind':'wire','pageId':'p','attributes':{'points':[[0,0],[10,0]],'net':'DELETED'}},{'kind':'wire','pageId':'p','attributes':{'points':[[0,20],[10,20]],'net':'ELBOW'}},{'kind':'wire','pageId':'p','attributes':{'points':[[10,20],[10,30]],'net':'ELBOW'}}]
  self.expected=unrelated_wire_nets(self.data,self.objects,'p','DELETED')
 def test_complete_untouched_group_preserved_after_target_delete(self):
  self.assertEqual(len(self.expected),2);verify_unrelated_wire_nets(self.data,self.objects[1:],self.expected)
 def test_real_failure_pattern_empty_names_is_rejected(self):
  rows=copy.deepcopy(self.objects[1:])
  for row in rows:row['attributes']['net']=''
  with self.assertRaises(CadenceError) as error:verify_unrelated_wire_nets(self.data,rows,self.expected)
  self.assertEqual(error.exception.code,'unrelated_wire_net_changed')
 def test_unrelated_missing_segment_or_renamed_net_refused(self):
  for rows in (self.objects[1:2],[{**self.objects[1],'attributes':{**self.objects[1]['attributes'],'net':'NEW'}},self.objects[2]]):
   with self.subTest(rows=rows),self.assertRaises(CadenceError):verify_unrelated_wire_nets(self.data,rows,self.expected)
 def test_wire_orientation_does_not_change_network_identity(self):
  rows=copy.deepcopy(self.objects[1:])
  for row in rows:row['attributes']['points'].reverse()
  verify_unrelated_wire_nets(self.data,rows,self.expected)
 def test_editor_endpoint_change_is_refused_before_gui_or_native_work(self):
  writer=object.__new__(CaptureWireEdits)
  with self.assertRaises(CadenceError) as error:writer.plan('s','w','set_endpoints',[],gui_session_id='gui',host_project='project')
  self.assertEqual(error.exception.code,'unsupported_editor_operation')
 def test_occurrence_requires_explicit_gui_and_bounded_text(self):
  writer=object.__new__(CaptureWireAdds)
  for occurrence in ('halfadd_A','bad\nname'):
   with self.assertRaises(CadenceError) as error:writer.plan('s','p',[0,0],[1,0],'NET',[],editor_occurrence=occurrence)
   self.assertEqual(error.exception.code,'invalid_editor_occurrence')
 def test_started_editor_delete_does_not_signal_process(self):
  writer=object.__new__(CaptureWireEdits);writer._load=lambda _: (None,None,{'digest':'d','state':'started','plan':{'payload':{'editorHost':{}}}})
  with self.assertRaises(CadenceError) as error:writer.cancel('a'*32,'d')
  self.assertEqual(error.exception.code,'too_late')

if __name__=='__main__':unittest.main()
