import copy,unittest
from cadence_mcp.capture_titleblock_vectors import normalize_titleblock_vectors
from cadence_mcp.core import CadenceError
TARGET={'objectId':'s/p/titleblock-1','pageId':'s/p','nativeId':17,'attributes':{'name':'T','location':[10,20],'rotationCode':0,'mirrorCode':0}}
def raw():
 return {'nativeId':17,'name':'T','sourceSymbol':'S','location':[10,20],'rotationCode':0,'mirrorCode':0,'vectors':[{'index':0,'nativeId':None,'nativeTypeCode':41,'kind':'line','location':[10,20],'rotationCode':0,'mirrorCode':0,'localDescriptor':['line',[0,0],[30,40],0,0],'pageControlPoints':[[10,20],[40,60]]}]}
class TitleblockVectors(unittest.TestCase):
 def test_identity_and_copy_do_not_invent_native_vector_ids(self):
  d=raw();out=normalize_titleblock_vectors(d,TARGET);self.assertEqual(out[0]['objectId'],'s/p/titleblock-1/vector-1');self.assertEqual(out[0]['titleblockId'],TARGET['objectId']);self.assertIsNone(out[0]['nativeId']);out[0]['pageControlPoints'][0][0]=99;self.assertEqual(d,raw())
 def test_foreign_header_and_pose_refused(self):
  for k,v in [('nativeId',18),('name','foreign'),('location',[0,0]),('rotationCode',1),('mirrorCode',1),('sourceSymbol',''),('rotationCode',False),('mirrorCode',False)]:
   d=raw();d[k]=v
   with self.subTest(k=k),self.assertRaises(CadenceError):normalize_titleblock_vectors(d,TARGET)
 def test_row_pose_must_match_header(self):
  d=raw();d['vectors'][0]['location']=[0,0]
  with self.assertRaises(CadenceError):normalize_titleblock_vectors(d,TARGET)
 def test_missing_or_extra_header_refused(self):
  for d in [dict(raw(),extra=1),{k:v for k,v in raw().items() if k!='name'}]:
   with self.assertRaises(CadenceError):normalize_titleblock_vectors(d,TARGET)
 def test_unordered_indices_or_incomplete_points_refused(self):
  for k,v in [('index',1),('pageControlPoints',[[10,20]]),('nativeId',12)]:
   d=raw();d['vectors'][0][k]=v
   with self.subTest(k=k),self.assertRaises(CadenceError):normalize_titleblock_vectors(d,TARGET)
 def test_unsupported_and_empty_definitions_explicit(self):
  d=raw();d['vectors'][0].update(kind='unsupported',localDescriptor=None,pageControlPoints=[]);self.assertEqual(normalize_titleblock_vectors(d,TARGET)[0]['kind'],'unsupported');d['vectors']=[];self.assertEqual(normalize_titleblock_vectors(d,TARGET),[])
