import copy,threading,unittest
from unittest.mock import patch
from cadence_mcp.capture_occurrence_properties import validate_layers,query_occurrence_properties
from cadence_mcp.core import CadenceError
def fixture():return {'effective':[{'name':'Value','value':'OCC_A_VALUE'}],'user':[{'name':'Value','value':'OCC_A_VALUE'}],'definition':{'nativeId':123,'reference':'U3','fullReference':'U3A','deviceDesignator':'A','kind':'placed','effective':[{'name':'Value','value':'74LS86'}],'user':[]}}
class OccurrenceLayerTests(unittest.TestCase):
 def test_override_and_definition_are_not_merged(self):
  result=validate_layers(fixture(),False);self.assertEqual(result['effective'][0]['value'],'OCC_A_VALUE');self.assertEqual(result['definition']['effective'][0]['value'],'74LS86')
 def test_duplicate_property_names_in_any_layer_refused(self):
  for owner,layer in [('occ','effective'),('occ','user'),('def','effective')]:
   value=fixture();target=value if owner=='occ' else value['definition'];target[layer].append(copy.deepcopy(target[layer][0]))
   with self.subTest(owner=owner,layer=layer),self.assertRaises(CadenceError):validate_layers(value,False)
 def test_root_and_component_definition_contexts_are_distinct(self):
  with self.assertRaises(CadenceError):validate_layers(fixture(),True)
  value=fixture();value['definition']=None
  with self.assertRaises(CadenceError):validate_layers(value,False)
  self.assertEqual(validate_layers(value,True)['definition'],None)
 def test_counts_and_string_budget_refused(self):
  for props in ([{'name':str(i),'value':''} for i in range(513)],[{'name':'Value','value':'x'*16385}]):
   value=fixture();value['effective']=props
   with self.assertRaises(CadenceError):validate_layers(value,False)
 def test_definition_and_layer_shapes_strict(self):
  for field,value in [('nativeId',True),('fullReference',[]),('kind','unknown')]:
   data=fixture();data['definition'][field]=value
   with self.subTest(field=field),self.assertRaises(CadenceError):validate_layers(data,False)
  data=fixture();data['user'][0]['eval']='x'
  with self.assertRaises(CadenceError):validate_layers(data,False)
 def test_valid_literal_values_and_layer_order_preserved(self):
  data=fixture();data['user']=[{'name':'Z','value':'中文[x]$;\nEND'},{'name':'A','value':''}];result=validate_layers(data,False);self.assertEqual(result['user'],[{'name':'A','value':''},{'name':'Z','value':'中文[x]$;\nEND'}])
 def test_unsafe_root_and_unknown_occurrence_refused_before_worker(self):
  class Capture:
   lock=threading.RLock()
   def _session(self,sid):return {'hierarchy':[{'occurrenceId':'occ-1','parentId':None}]}
  with patch('cadence_mcp.capture_occurrence_properties.get_hierarchy'),patch('cadence_mcp.capture_occurrence_properties.run_tcl') as worker:
   for ident,code in [('occ-1','capability_unavailable'),('occ-999','object_not_found')]:
    with self.assertRaises(CadenceError) as error:query_occurrence_properties(Capture(),'sid',ident)
    self.assertEqual(error.exception.code,code)
   worker.assert_not_called()
