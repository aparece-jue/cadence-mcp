import copy,unittest
from cadence_mcp.capture_alias_edit import alias_changes
from cadence_mcp.core import CadenceError
class AliasEditTests(unittest.TestCase):
 def fixture(self):return [{'kind':'wire','objectId':'w','pageId':'p','attributes':{'points':[[0,0],[100,0]],'net':'A'}},{'kind':'alias','objectId':'a','pageId':'p','attributes':{'wireId':'w','name':'A','location':[0,0]}},{'kind':'alias','objectId':'b','pageId':'p','attributes':{'wireId':'w','name':'OTHER','location':[100,0]}}]
 def test_edit_changes_only_selected_alias_and_keeps_input_immutable(self):
  rows=self.fixture();old=copy.deepcopy(rows);_,expected,name,loc=alias_changes(rows,rows[1],'set','B',[50,0]);self.assertEqual(rows,old);self.assertEqual(expected[0],rows[0]);self.assertEqual(expected[2],rows[2]);self.assertEqual(expected[1]['attributes'],{'wireId':'w','name':'B','location':[50,0]})
 def test_delete_preserves_wire_and_other_attached_alias(self):
  rows=self.fixture();_,expected,_,_=alias_changes(rows,rows[1],'delete',None,None);self.assertEqual(expected,[rows[0],rows[2]]);self.assertEqual(len(rows),3)
 def test_invalid_anchor_noop_bus_name_and_semantic_conflict_refused(self):
  rows=self.fixture()
  for op,name,loc in [('set',None,None),('set','B',[50,1]),('set','DATA[7..0]',None),('set','OTHER',[100,0]),('delete','B',None),('bad',None,None)]:
   with self.assertRaises(CadenceError):alias_changes(rows,rows[1],op,name,loc)
