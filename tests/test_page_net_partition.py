import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.page_net_partition import page_partition
def wire(page='P',group='g',name='N'):return {'kind':'wire','schematicName':'S','pageName':page,'group':group,'netName':name,'nativeId':12,'points':[[0,0],[10,0]]}
def pin(ref='R1',group='g',name='N'):return {'kind':'pin','schematicName':'S','pageName':'P','group':group,'netName':name,'reference':ref,'number':'1','name':'A'}
class PagePartitionTests(unittest.TestCase):
 def test_group_ids_and_enumeration_do_not_change_semantic_memberships(self):
  old=[wire(),pin()];new=copy.deepcopy(old)
  for r in new:r['group']='fresh'
  new.reverse();self.assertEqual(page_partition(old),page_partition(new))
 def test_only_selected_native_group_name_can_change(self):
  old=[wire(),pin(),pin('R2','h','OTHER')];new=copy.deepcopy(old)
  for r in new[:2]:r['netName']='GENERATED'
  self.assertEqual(page_partition(old,['S','P',12],'N'),page_partition(new,['S','P',12]))
  new[2]['netName']='WRONG';self.assertNotEqual(page_partition(old,['S','P',12]),page_partition(new,['S','P',12]))
  with self.assertRaises(CadenceError):page_partition(new,['S','P',12],'N')
 def test_partition_split_is_detected_even_with_equal_names(self):
  old=[wire(),pin()];new=copy.deepcopy(old);new[1]['group']='separate'
  self.assertNotEqual(page_partition(old),page_partition(new))
 def test_same_native_group_token_is_separate_on_different_pages(self):
  value=page_partition([wire(),wire('OTHER')]);self.assertEqual(len(value['groups']),2)
 def test_ambiguous_keys_invalid_fields_and_unknown_target_refused(self):
  for rows in ([wire(),wire()], [{**wire(),'nativeId':True}], [{**pin(),'group':None}], [{**wire(),'extra':0}]):
   with self.assertRaises(CadenceError):page_partition(rows)
  with self.assertRaises(CadenceError):page_partition([wire()],['S','P',99])
