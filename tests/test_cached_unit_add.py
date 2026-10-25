import copy,unittest
from cadence_mcp.capture_cached_unit_add import select_missing_device
from cadence_mcp.core import CadenceError

def sample():
 cache={'package':[{'objectId':'p','name':'CACHE','size':2}],'device':[{'objectId':'b','packageId':'p','designator':'B'}],'part':[{'objectId':'partB','packageId':'p','deviceId':'b'}]}
 owner={'partId':'owner','kind':'placed','packageSize':2,'isExternalDesignPart':False,'packageName':'CACHE','reference':'U1','referenceDesignator':'U1A','deviceDesignator':'A','schematicName':'TOP'}
 return cache,{'owner':owner}

class CachedUnitAddTests(unittest.TestCase):
 def test_missing_device_uses_existing_owner_reference_and_cache(self):
  cache,units=sample();owner,pkg,dev,part,group=select_missing_device(cache,units,'owner','partB');self.assertEqual((owner['reference'],pkg['name'],dev['designator'],len(group)),('U1','CACHE','B',1))
 def test_device_already_present_is_not_placed_twice(self):
  cache,units=sample();units['b']={**units['owner'],'deviceDesignator':'B','referenceDesignator':'U1B'}
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'unit_already_placed')
 def test_full_unit_reference_collision_with_other_base_is_refused(self):
  cache,units=sample();units['block']={**units['owner'],'reference':'U1B','referenceDesignator':'','kind':'drawn'}
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'unit_already_placed')
 def test_foreign_cache_package_cannot_be_added_to_owner(self):
  cache,units=sample();cache['package'][0]['name']='OTHER'
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'cache_package_mismatch')
 def test_unannotated_reference_cannot_define_physical_group(self):
  cache,units=sample();units['owner']['reference']='U?'
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'invalid_reference')
 def test_external_owner_is_not_treated_as_internal_cache(self):
  cache,units=sample();units['owner']['isExternalDesignPart']=True
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'unsupported_unit_scope')
 def test_duplicate_existing_devices_make_group_ambiguous(self):
  cache,units=sample();units['duplicate']=copy.deepcopy(units['owner'])
  with self.assertRaises(CadenceError) as got:select_missing_device(cache,units,'owner','partB')
  self.assertEqual(got.exception.code,'ambiguous_package_group')

if __name__=='__main__':unittest.main()
