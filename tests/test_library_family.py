import copy,unittest
from pydantic import ValidationError
from cadence_mcp.core import CadenceError
from cadence_mcp.library_create import validate_spec,expected_graph,physical_pad_count
from cadence_mcp.server import LibraryFamilySpec,LibraryCreationSpec
from test_library_create import spec

def family():
 a=spec();b=copy.deepcopy(a);b.update(packageName='TEST_QFN',footprint='QFN_1')
 b['symbols'][0].update(cellName='C_QFN',partName='P_QFN.Normal');b['devices'][0]['cellName']='C_QFN'
 return {'packages':[a,b]}

class LibraryFamilyTests(unittest.TestCase):
 def test_original_schema_and_graph_remain_unchanged(self):
  self.assertEqual(validate_spec(spec()),spec());self.assertIn('pins',expected_graph(spec()));self.assertEqual(physical_pad_count(spec()),1)
 def test_pad_numbers_are_package_scoped_not_globally_merged(self):
  f=family();before=copy.deepcopy(f);self.assertEqual(physical_pad_count(validate_spec(f)),2);self.assertEqual(f,before);self.assertEqual(len(expected_graph(f)['packages']),2)
 def test_case_colliding_names_and_cross_package_native_names_refused(self):
  for kind in ('package','cell','part'):
   f=family()
   if kind=='package':f['packages'][1]['packageName']='test'
   if kind=='cell':f['packages'][1]['symbols'][0]['cellName']='C';f['packages'][1]['devices'][0]['cellName']='C'
   if kind=='part':f['packages'][1]['symbols'][0]['partName']='p.normal'
   with self.subTest(kind=kind),self.assertRaises(CadenceError):validate_spec(f)
 def test_nested_empty_single_and_extra_keys_refused(self):
  for f in ({'packages':[]},{'packages':[spec()]},{'packages':[family(),spec()]},{**family(),'eval':'x'}):
   with self.assertRaises(CadenceError):validate_spec(f)
 def test_each_variant_requires_complete_physical_map(self):
  f=family();f['packages'][1]['devices'][0]['mapping']=[]
  with self.assertRaises(CadenceError):validate_spec(f)
 def test_public_union_shapes_are_strict(self):
  self.assertEqual(len(LibraryFamilySpec.model_validate(family()).packages),2);LibraryCreationSpec.model_validate(spec())
  with self.assertRaises(ValidationError):LibraryFamilySpec.model_validate({**family(),'script':'x'})
 def test_declared_oracle_changes_when_one_package_mapping_changes(self):
  f=family();before=expected_graph(f);f['packages'][1]['devices'][0]['mapping'][0]['number']='A1';self.assertNotEqual(expected_graph(f),before)
 def test_global_ordered_reader_mode_includes_plain_package_vectors(self):
  f=family();f['packages'][1]['symbols'][0]['vectors']=[{'kind':'ellipse','bounds':[0,0,10,20],'style':0,'width':0,'fill':1,'hatch':0}]
  graph=expected_graph(validate_spec(f))
  self.assertTrue(all('orderedVectors' in g['meta']['symbols'][0] for g in graph['packages']))
