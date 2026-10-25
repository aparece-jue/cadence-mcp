import copy,unittest
from cadence_mcp.capture_unit_edit import identities_digest,cache_graph_digest,plan_unit_edit,validate_physical_bindings
from cadence_mcp.core import CadenceError

def identities():
 return {name:{'partId':name,'nativeId':number,'schematicName':'TOP','pageName':'PAGE','reference':'U1','kind':'placed','isExternalDesignPart':False,'packageName':'CACHE','packageSize':2,'deviceDesignator':name,'referenceDesignator':'U1'+name} for number,name in enumerate(('A','B'),1)}
def cache():
 return {'package':[{'objectId':'p','name':'CACHE','size':2,'homogeneous':True,'footprint':'FP'}],'device':[{'objectId':'d','packageId':'p','designator':'A','position':0,'cellId':'c'}],'cell':[{'objectId':'c','name':'CELL'}],'part':[{'objectId':'v','deviceId':'d','cellId':'c','name':'CELL.Normal'}],'pin':[{'partId':'v','position':0,'number':'8','name':'VCC','pinType':7,'visible':False,'shared':True,'swapId':-1,'hotSpot':[0,-20]}]}

class UnitEditContractTests(unittest.TestCase):
 def test_same_base_reference_does_not_hide_changed_unit_full_reference(self):
  old=identities();new=copy.deepcopy(old);new['B']['referenceDesignator']='U2B';self.assertNotEqual(identities_digest(old),identities_digest(new))
 def test_deletion_filters_native_identity_not_shared_base_reference(self):
  old=identities();self.assertEqual(identities_digest(old,1),identities_digest({'B':old['B']}));self.assertNotEqual(identities_digest(old,1),identities_digest({'A':old['A']}))
 def test_ordinal_part_ids_may_change_after_unit_delete(self):
  old=identities();new=copy.deepcopy(old)
  for r in new.values():r['partId']='new-'+r['partId']
  self.assertEqual(identities_digest(old),identities_digest(new))
 def test_unrelated_unit_package_ownership_is_checked(self):
  old=identities();new=copy.deepcopy(old);new['B']['packageName']='OTHER';self.assertNotEqual(identities_digest(old),identities_digest(new))
 def test_cache_renumbered_ordinal_ids_preserve_semantic_graph(self):
  old=cache();new=copy.deepcopy(old);new['package'][0]['objectId']='p2';new['device'][0].update(objectId='d2',packageId='p2',cellId='c2');new['cell'][0]['objectId']='c2';new['part'][0].update(objectId='v2',deviceId='d2',cellId='c2');new['pin'][0]['partId']='v2';self.assertEqual(cache_graph_digest(old),cache_graph_digest(new))
 def test_cache_shared_flag_physical_number_and_swap_are_not_lost(self):
  old=cache()
  for key,value in [('shared',False),('number','7'),('swapId',3),('visible',True)]:
   new=copy.deepcopy(old);new['pin'][0][key]=value;self.assertNotEqual(cache_graph_digest(old),cache_graph_digest(new))
 def test_shared_pad_cannot_be_disconnected_on_one_unit_only(self):
  units=identities();data={'pin':[{'partId':'A','number':'8','connected':True,'net':'VCC'},{'partId':'B','number':'8','connected':False,'net':''}]}
  with self.assertRaises(CadenceError) as got:validate_physical_bindings(data,units)
  self.assertEqual(got.exception.code,'shared_pin_binding_conflict')
 def test_legacy_and_unit_expectations_are_mutually_exclusive(self):
  with self.assertRaises(CadenceError) as got:plan_unit_edit(None,'sid','part','delete',[{'legacy':True}],None,None,None,None,[])
  self.assertEqual(got.exception.code,'invalid_expectations')

if __name__=='__main__':unittest.main()
