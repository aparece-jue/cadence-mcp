import copy,unittest
from cadence_mcp.capture_cached_unit_add import target_page,select_missing_device,verify_crosspage_shared_bindings
from cadence_mcp.core import CadenceError
from test_cached_unit_add import sample

def pages():
 return {'page':[{'objectId':'source','schematicId':'s1','name':'PAGE'},{'objectId':'target','schematicId':'s1','name':'NEXT'},{'objectId':'foreign','schematicId':'s2','name':'NEXT'}]}

class CachedUnitCrossPageTests(unittest.TestCase):
 def test_omitted_target_retains_owner_page(self):
  owner,target=target_page(pages(),{'pageId':'source'},None);self.assertEqual(owner,target)
 def test_explicit_target_in_same_schematic_is_selected(self):
  owner,target=target_page(pages(),{'pageId':'source'},'target');self.assertEqual(owner['objectId'],'source');self.assertEqual(target['objectId'],'target')
 def test_same_name_foreign_schematic_does_not_define_same_physical_group(self):
  with self.assertRaises(CadenceError) as error:target_page(pages(),{'pageId':'source'},'foreign')
  self.assertEqual(error.exception.code,'unsupported_unit_scope')
 def test_foreign_or_stale_page_id_refused(self):
  with self.assertRaises(CadenceError) as error:target_page(pages(),{'pageId':'source'},'old-snapshot-page')
  self.assertEqual(error.exception.code,'object_not_found')
 def test_target_selection_does_not_mutate_snapshot(self):
  data=pages();before=copy.deepcopy(data);target_page(data,{'pageId':'source'},'target');self.assertEqual(data,before)
 def test_device_already_on_another_page_remains_occupied(self):
  cache,units=sample();units['owner']['pageName']='FIRST';units['b']={**units['owner'],'deviceDesignator':'B','referenceDesignator':'U1B','pageName':'SECOND'}
  with self.assertRaises(CadenceError) as error:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(error.exception.code,'unit_already_placed')
 def test_same_labels_on_different_native_nets_do_not_certify_shared_pad(self):
  units={k:{'reference':'U1','referenceDesignator':'U1'+k,'schematicName':'TOP','pageName':k,'packageName':'C'} for k in ('A','B')};data={'pin':[{'partId':k,'number':'8','name':'VCC'} for k in units]};bindings=[{'kind':'pin','schematicName':'TOP','pageName':k,'reference':'U1'+k,'number':'8','name':'VCC','group':'native-'+k,'netName':'VCC'} for k in units];p={'reference':'U1','schematicName':'TOP','cacheName':'C'}
  with self.assertRaises(CadenceError):verify_crosspage_shared_bindings(data,units,bindings,p)
  bindings[1]['group']=bindings[0]['group'];verify_crosspage_shared_bindings(data,units,bindings,p)
 def test_unbound_shared_pads_do_not_fabricate_connected_native_identity(self):
  units={k:{'reference':'U1','referenceDesignator':'U1'+k,'schematicName':'TOP','pageName':k,'packageName':'C'} for k in ('A','B')};data={'pin':[{'partId':k,'number':'8','name':'VCC'} for k in units]};bindings=[{'kind':'pin','schematicName':'TOP','pageName':k,'reference':'U1'+k,'number':'8','name':'VCC','group':None,'netName':''} for k in units];verify_crosspage_shared_bindings(data,units,bindings,{'reference':'U1','schematicName':'TOP','cacheName':'C'})
