import copy,unittest
from pydantic import ValidationError
from cadence_mcp.core import CadenceError
from cadence_mcp.library_pin_style import FLAGS,validate_style,expected_styles,normalize_styles
from cadence_mcp.server import LibraryPinStyleChange

def rows():
 flags={k:False for k in FLAGS};flags.update(long=True,visible=True,numberVisible=True)
 return [{'scope':['P',dev,i,'C',part,pos],'flags':copy.deepcopy(flags)} for dev,i,part,pos in [('A',0,'C.Normal',0),('B',1,'C.Normal',0),('A',0,'C.Convert',0),('A',0,'C.Normal',1)]]

class PinStyleTests(unittest.TestCase):
 def test_shared_symbol_flags_change_together_and_other_views_pins_stay(self):
  source=rows();before=copy.deepcopy(source);expected,changes,old=expected_styles(source,source[0]['scope'],{'clock':True,'dot':True})
  self.assertEqual(len(changes),2);self.assertTrue(all(r['flags']['clock'] for r in expected[:2]));self.assertEqual(expected[2:],source[2:]);self.assertEqual(source,before);self.assertFalse(old['clock'])
 def test_combined_visibility_is_part_of_complete_flag_expectation(self):
  source=rows();expected,changes,_=expected_styles(source,source[0]['scope'],{'long':False},False,source_pin_type=4)
  self.assertFalse(expected[0]['flags']['visible']);self.assertTrue(expected[0]['flags']['global']);self.assertFalse(expected[1]['flags']['long']);self.assertEqual(len(changes),2)
 def test_empty_unknown_nonboolean_fields_refused(self):
  for style in ({},{'global':True},{'clock':1},{'dot':'true'},{'long':None}):
   with self.subTest(style=style),self.assertRaises(CadenceError):validate_style(style)
 def test_conflicting_shared_native_definitions_are_ambiguous(self):
  source=rows();source[1]['flags']['dot']=True
  with self.assertRaises(CadenceError) as error:expected_styles(source,source[0]['scope'],{'clock':True})
  self.assertEqual(error.exception.code,'ambiguous_pin_style')
 def test_no_change_has_no_affected_views(self):
  source=rows();expected,changes,_=expected_styles(source,source[0]['scope'],{'long':True});self.assertEqual(expected,source);self.assertEqual(changes,[])
 def test_public_model_rejects_numeric_booleans_and_extra_setter_names(self):
  for style in ({'clock':1},{'SetIsGlobal':True}):
   with self.assertRaises(ValidationError):LibraryPinStyleChange.model_validate(style)
  self.assertEqual(LibraryPinStyleChange.model_validate({'dot':False}).model_dump(exclude_none=True),{'dot':False})
 def test_visible_power_pin_keeps_global_and_type_change_is_previewed(self):
  source=rows()
  for row in source[:2]:row['flags'].update(visible=False,**{'global':True})
  expected,_,_=expected_styles(source,source[0]['scope'],{'clock':True},True,source_pin_type=7)
  self.assertTrue(expected[0]['flags']['global']);self.assertTrue(expected[0]['flags']['visible'])
  source=rows();expected,_,_=expected_styles(source,source[0]['scope'],{'clock':True},source_pin_type=4,pin_type=7);self.assertTrue(expected[0]['flags']['global'])
 def test_native_rows_bind_semantics_and_refuse_incomplete_or_nonboolean_flags(self):
  base={'package':[{'objectId':'p','name':'P','size':1,'homogeneous':True,'footprint':'FP'}],'device':[{'objectId':'d','packageId':'p','designator':'','position':0,'cellId':'c'}],'cell':[{'objectId':'c','deviceId':'d','packageId':'p','name':'C'}],'part':[{'objectId':'t','cellId':'c','deviceId':'d','packageId':'p','name':'C.Normal'}],'pin':[{'objectId':'q','partId':'t','deviceId':'d','packageId':'p','name':'IN','position':0,'number':'1','pinType':0,'visible':True,'shared':False,'swapId':0,'hotSpot':[-20,0]}]}
  raw=copy.deepcopy(base);raw['pin'][0]['objectId']='different-native-order-id';raw['pinStyles']=[{'pinId':'different-native-order-id','flags':rows()[0]['flags']}]
  normalized=normalize_styles(raw,base);self.assertEqual(normalized[0]['scope'],['P','',0,'C','C.Normal',0])
  for entries in ([],raw['pinStyles']*2,[{'pinId':'different-native-order-id','flags':{**rows()[0]['flags'],'clock':1}}]):
   bad=copy.deepcopy(raw);bad['pinStyles']=entries
   with self.assertRaises(CadenceError):normalize_styles(bad,base)
  raw['pin'][0]['pinType']=1
  with self.assertRaises(CadenceError) as error:normalize_styles(raw,base)
  self.assertEqual(error.exception.code,'target_changed')
