import copy,unittest
from cadence_mcp.capture_display_fonts import font_fields,normalize_fonts,target_font
from cadence_mcp.core import CadenceError

def fixture():
 units={'a':{'nativeId':1},'b':{'nativeId':2}}
 font=font_fields({'height':-17,'weight':700,'italic':True,'underline':True})
 return [{'nativeId':2,'fonts':[]},{'nativeId':1,'fonts':[{'name':'Part Reference','font':font,'fontDefault':0,'defaultFontType':1}]}],units

class DisplayFontTests(unittest.TestCase):
 def test_complete_descriptor_order_and_bool_encoding(self):
  self.assertEqual(font_fields({'height':-17,'weight':700,'italic':True,'underline':True}),['Arial',-17,0,0,0,700,1,1,0,0,7,0,1,16])
 def test_invalid_or_extra_requested_fields_rejected(self):
  for value in ({'height':0},{'height':True},{'weight':1001},{'quality':256},{'faceName':'x\x00y'},{'faceName':'x\ny'},{'extra':1},{'italic':1}):
   with self.subTest(value=value),self.assertRaises(CadenceError):font_fields(value)
 def test_literal_name_never_interpreted(self):
  self.assertEqual(font_fields({'faceName':'[x]$;{face}'})[0],'[x]$;{face}')
 def test_normalization_preserves_inheritance_and_no_display_instances(self):
  rows,units=fixture();before=copy.deepcopy(rows);result=normalize_fonts(rows,units)
  self.assertEqual([r['nativeId'] for r in result],[1,2]);self.assertEqual(result[1]['fonts'],[]);self.assertEqual(rows,before)
  self.assertEqual(target_font(result,units['a'],'Part Reference')[1],-17)
 def test_incomplete_duplicate_or_external_instance_rejected(self):
  for kind in ('missing','duplicate','external','boolid'):
   rows,units=fixture()
   if kind=='missing':rows.pop()
   if kind=='duplicate':rows[0]['nativeId']=1
   if kind=='external':rows[0]['nativeId']=99
   if kind=='boolid':rows[0]['nativeId']=True
   with self.subTest(kind=kind),self.assertRaises(CadenceError):normalize_fonts(rows,units)
 def test_untrusted_font_shape_and_inheritance_rejected(self):
  for kind in ('short','bool','flag','type','duplicate','extra'):
   rows,units=fixture();prop=rows[1]['fonts'][0]
   if kind=='short':prop['font'].pop()
   if kind=='bool':prop['font'][1]=False
   if kind=='flag':prop['fontDefault']=2
   if kind=='type':prop['defaultFontType']='1'
   if kind=='duplicate':rows[1]['fonts'].append(copy.deepcopy(prop))
   if kind=='extra':prop['eval']='x'
   with self.subTest(kind=kind),self.assertRaises(CadenceError):normalize_fonts(rows,units)
 def test_exact_display_name_and_missing_target(self):
  rows,units=fixture()
  for name in ('Reference','Part ReferenceA','',None):
   with self.subTest(name=name),self.assertRaises(CadenceError):target_font(rows,units['a'],name)
