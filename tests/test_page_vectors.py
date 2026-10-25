import copy,unittest
from cadence_mcp.capture_page_vectors import normalize_page_vectors,control_point_count
from cadence_mcp.core import CadenceError
def row():return {'index':0,'nativeId':7,'nativeTypeCode':56,'kind':'line','location':[100,200],'rotationCode':1,'mirrorCode':1,'localDescriptor':['line',[-10,5],[50,35],2,1],'pageControlPoints':[[105,190],[135,250]]}
class PageVectorTests(unittest.TestCase):
 def test_native_descriptor_and_control_identity_preserved(self):
  source=[row()];before=copy.deepcopy(source);result=normalize_page_vectors(source,'p')
  self.assertEqual(result[0]['objectId'],'p/graphic-1');self.assertEqual(result[0]['pageControlPoints'],[[105,190],[135,250]]);result[0]['localDescriptor'][1][0]=999;self.assertEqual(source,before)
 def test_unknown_graphics_explicit_and_not_dropped(self):
  value={**row(),'kind':'unsupported','localDescriptor':None,'pageControlPoints':[]};self.assertEqual(normalize_page_vectors([value],'p')[0]['kind'],'unsupported')
  value['localDescriptor']=['line',[0,0],[1,1],0,0]
  with self.assertRaises(CadenceError):normalize_page_vectors([value],'p')
 def test_malformed_identity_and_pose_rejected(self):
  for key,value in [('index',1),('index',False),('nativeId',False),('location',[0]),('rotationCode',9),('mirrorCode',True)]:
   source=row();source[key]=value
   with self.subTest(key=key,value=value),self.assertRaises(CadenceError):normalize_page_vectors([source],'p')
 def test_full_control_point_coverage_required(self):
  source=row();source['pageControlPoints'].pop()
  with self.assertRaises(CadenceError):normalize_page_vectors([source],'p')
 def test_descriptor_kind_and_fields_must_match(self):
  for field,value in [('kind','box'),('localDescriptor',['line',[0,0],[1,1],False,0]),('localDescriptor',['unknown'])]:
   source=row();source[field]=value
   with self.subTest(field=field),self.assertRaises(CadenceError):normalize_page_vectors([source],'p')
 def test_boundaries_empty_scope_and_native_order(self):
  self.assertEqual(normalize_page_vectors([],'p'),[])
  with self.assertRaises(CadenceError):normalize_page_vectors([row()]*4097,'p')
  second={**row(),'index':1};self.assertEqual([r['index'] for r in normalize_page_vectors([row(),second],'p')],[0,1])
 def test_coordinate_roles_have_expected_cardinality(self):
  for descriptor,count in [(['line'],2),(['box'],4),(['ellipse'],4),(['arc'],6),(['polygon',[[1,2],[3,4]]],2),(['text'],5),(['bitmap'],5)]:self.assertEqual(control_point_count(descriptor),count)
