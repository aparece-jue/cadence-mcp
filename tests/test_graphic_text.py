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

class GraphicTextEditTests(unittest.TestCase):
 def writer(self,kind='text'):
  import threading
  from types import SimpleNamespace
  from cadence_mcp.capture_graphic_text import CaptureGraphicTexts
  self.row={'objectId':'p/graphic-1','pageId':'p','index':0,'nativeId':73,'nativeTypeCode':61,'kind':kind,'location':[0,0],'rotationCode':0,'mirrorCode':0,'localDescriptor':['text','same'],'pageControlPoints':[]}
  self.session={'data':{'page':[{'objectId':'p','schematicId':'s','name':'page'}]},'pageVectors':{'p':[self.row]}}
  w=object.__new__(CaptureGraphicTexts);w.capture=SimpleNamespace(lock=threading.RLock(),_session=lambda sid:self.session);return w
 def test_delete_binds_source_index_and_native_id(self):
  w=self.writer()
  with patch('cadence_mcp.capture_graphic_text.page_rows'),patch.object(w,'_plan',return_value={'planned':True}) as create:
   self.assertEqual(w.plan_edit('s','p/graphic-1','delete'),{'planned':True});edit=create.call_args.args[-1];self.assertEqual(edit['targetIndex'],0);self.assertEqual(edit['targetNativeId'],73);self.assertIsNone(create.call_args.args[2])
 def test_update_requires_complete_strict_declaration(self):
  w=self.writer();change={'text':'new','location':[300,450],'width':180,'height':40,'font':{},'rotation':1,'mirror':1}
  with patch('cadence_mcp.capture_graphic_text.page_rows'),patch.object(w,'_plan',return_value={}) as create:
   w.plan_edit('s','p/graphic-1','update',change);self.assertEqual(create.call_args.args[2]['pageControlPoints'][0],[300,450]);self.assertEqual(change['font'],{})
   for bad in ({**change,'mirror':True},{k:v for k,v in change.items() if k!='font'},{**change,'extra':'eval'}):
    with self.assertRaises(CadenceError):w.plan_edit('s','p/graphic-1','update',bad)
 def test_delete_forbids_change_and_nontext_foreign_huge_ids(self):
  w=self.writer('line')
  with patch('cadence_mcp.capture_graphic_text.page_rows'):
   for ident in ('p/graphic-1','p/graphic-2','other/graphic-1','p/graphic-'+('9'*5000)):
    with self.assertRaises(CadenceError):w.plan_edit('s',ident,'delete')
  with self.assertRaises(CadenceError):w.plan_edit('s','p/graphic-1','delete',{})
  with self.assertRaises(CadenceError):w.plan_edit('s','p/graphic-1','update')
 def test_replacement_preserves_order_and_duplicate_multiplicity(self):
  from types import SimpleNamespace
  from cadence_mcp.isolated_jobs import digest
  data={'page':[{'objectId':'p','schematicId':'s','name':'page'}],'schematic':[{'objectId':'s','name':'root'}]};cap=SimpleNamespace(_session=lambda sid:{'data':data});rows=[{'text':'duplicate'},{'text':'middle'},{'text':'duplicate'}]
  with patch('cadence_mcp.capture_graphic_text.page_rows',side_effect=lambda *args:copy.deepcopy(rows)):
   actual=graphic_state(cap,'s','p',{'text':'new'},1);self.assertEqual(actual,[{'scope':['root','page'],'digest':digest([rows[0],{'text':'new'},rows[2]])}]);self.assertEqual(rows[1],{'text':'middle'})
 def test_deletion_keeps_other_duplicate_and_order(self):
  from types import SimpleNamespace
  from cadence_mcp.isolated_jobs import digest
  data={'page':[{'objectId':'p','schematicId':'s','name':'page'}],'schematic':[{'objectId':'s','name':'root'}]};cap=SimpleNamespace(_session=lambda sid:{'data':data});rows=[{'text':'duplicate'},{'text':'middle'},{'text':'duplicate'}]
  with patch('cadence_mcp.capture_graphic_text.page_rows',side_effect=lambda *args:copy.deepcopy(rows)):
   self.assertEqual(graphic_state(cap,'s','p',None,0),[{'scope':['root','page'],'digest':digest(rows[1:])}])
