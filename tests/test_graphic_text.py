import copy,unittest
from unittest.mock import patch
from cadence_mcp.capture_graphic_text import declaration,page_rows,graphic_state
from cadence_mcp.core import CadenceError
class GraphicTextTests(unittest.TestCase):
 def test_inverse_pose_keeps_explicit_page_anchor(self):
  raw={(0,0):[300,450],(1,0):[-450,300],(2,0):[-300,-450],(3,0):[450,-300],(0,1):[-300,450],(1,1):[450,300],(2,1):[300,-450],(3,1):[-450,-300]}
  for (rotation,mirror),wanted in raw.items():
   d=declaration('literal [x]$;\n中文',[300,450],180,40,rotation,mirror,{})
   self.assertEqual(d['localDescriptor'][2],wanted);self.assertEqual(d['pageControlPoints'][0],[300,450]);self.assertEqual(d['location'],[0,0])
 def test_rejects_boolean_invalid_text_and_transformed_overflow(self):
  for text,loc,w,h,r,m in [('',[0,0],10,10,0,0),('a\x00b',[0,0],10,10,0,0),('a\rb',[0,0],10,10,0,0),('\ud800',[0,0],10,10,0,0),('a',[True,0],10,10,0,0),('a',[0,0],True,10,0,0),('a',[0,0],10,10,False,0),('a',[1000000,0],10,10,0,0)]:
   with self.assertRaises(CadenceError):declaration(text,loc,w,h,r,m,{})
 def test_font_quality_restriction_and_no_input_mutation(self):
  font={'height':-17,'weight':700,'underline':True};before=copy.deepcopy(font);d=declaration('x',[0,0],10,10,0,0,font);self.assertEqual(font,before);self.assertEqual(d['localDescriptor'][4][5],700)
  with self.assertRaises(CadenceError):declaration('x',[0,0],10,10,0,0,{'quality':2})
 def test_native_order_and_duplicate_graphics_are_preserved_without_ids(self):
  row={'objectId':'old','pageId':'p','nativeId':1,'nativeTypeCode':61,'index':0,'kind':'text','location':[0,0],'rotationCode':0,'mirrorCode':0,'localDescriptor':['text','x'],'pageControlPoints':[]}
  with patch('cadence_mcp.capture_graphic_text.query_page_vectors',return_value={'supportedGeometryComplete':True,'items':[row,row],'nextCursor':None}):
   out=page_rows(None,'s','p');self.assertEqual(len(out),2);self.assertNotIn('nativeId',out[0]);out[0]['localDescriptor'][1]='changed';self.assertEqual(row['localDescriptor'][1],'x')
 def test_unsupported_geometry_refused_instead_of_omitted(self):
  with patch('cadence_mcp.capture_graphic_text.query_page_vectors',return_value={'supportedGeometryComplete':False,'items':[],'nextCursor':None}):
   with self.assertRaises(CadenceError):page_rows(None,'s','p')
