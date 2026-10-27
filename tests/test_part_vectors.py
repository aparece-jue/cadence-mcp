import copy,unittest
from cadence_mcp.capture_part_vectors import normalize_part_vectors
from cadence_mcp.core import CadenceError
PART={'objectId':'s/p/part-1','reference':'U1'}
PAGE={'objectId':'s/p','name':'P'};SCH={'name':'S'}
def raw():
 return {'partId':PART['objectId'],'reference':'U1','pageName':'P','schematicName':'S','location':[10,20],'rotationCode':0,'mirrorCode':0,'boxes':[],'pins':[],
 'vectors':[{'index':0,'nativeId':None,'nativeTypeCode':41,'kind':'line','location':[10,20],'rotationCode':0,'mirrorCode':0,'localDescriptor':['line',[0,0],[30,40],0,0],'pageControlPoints':[[10,20],[40,60]]}]}
class PartVectors(unittest.TestCase):
 def test_revision_scoped_identity_does_not_invent_native_id(self):
  value=raw();out=normalize_part_vectors(value,PART,PAGE,SCH);self.assertEqual(out[0]['objectId'],'s/p/part-1/vector-1');self.assertIsNone(out[0]['nativeId']);self.assertEqual(out[0]['partId'],PART['objectId']);out[0]['pageControlPoints'][0][0]=99;self.assertEqual(value,raw())
 def test_foreign_target_and_parent_names_refused(self):
  for field in ('partId','reference','pageName','schematicName'):
   value=raw();value[field]='foreign'
   with self.subTest(field=field),self.assertRaises(CadenceError):normalize_part_vectors(value,PART,PAGE,SCH)
 def test_worker_pose_cannot_differ_from_vector_pose(self):
  value=raw();value['vectors'][0]['location']=[11,20]
  with self.assertRaises(CadenceError):normalize_part_vectors(value,PART,PAGE,SCH)
 def test_native_id_is_unavailable_not_a_guessed_integer(self):
  value=raw();value['vectors'][0]['nativeId']=1
  with self.assertRaises(CadenceError):normalize_part_vectors(value,PART,PAGE,SCH)
 def test_missing_control_point_and_unordered_index_rejected(self):
  for field,value in (('pageControlPoints',[[10,20]]),('index',1)):
   data=raw();data['vectors'][0][field]=value
   with self.subTest(field=field),self.assertRaises(CadenceError):normalize_part_vectors(data,PART,PAGE,SCH)
 def test_unsupported_row_is_retained_and_empty_part_is_explicit(self):
  value=raw();value['vectors'][0].update(kind='unsupported',localDescriptor=None,pageControlPoints=[])
  self.assertEqual(normalize_part_vectors(value,PART,PAGE,SCH)[0]['kind'],'unsupported')
  value['vectors']=[];self.assertEqual(normalize_part_vectors(value,PART,PAGE,SCH),[])
