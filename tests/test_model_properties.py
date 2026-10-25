import copy,unittest
from cadence_mcp.capture_edit import validate_property_change,property_snapshot,expected_property_snapshot
from cadence_mcp.core import CadenceError

def rows():
 return [{'partId':'p1','schematicName':'ROOT','pageName':'PAGE','reference':'D1','properties':[{'name':'Value','value':'DIODE'},{'name':'Implementation','value':'OLD'},{'name':'TC1','value':'0'}]},
         {'partId':'p2','schematicName':'AUX','pageName':'PAGE','reference':'D1','properties':[{'name':'Implementation','value':'OTHER'}]}]

class ModelPropertyTests(unittest.TestCase):
 def test_model_identifier_and_finite_coefficients(self):
  for model in ('D1N4148','1N4002','MCP_TEST.+-'):validate_property_change('Implementation',model)
  for v in ('0','-.001','+1.2e-3','-4E+6','2147483648'):validate_property_change('TC1',v);validate_property_change('TC2',v)
  for name,v in [('Implementation',''),('Implementation','bad model'),('Implementation','x\n.end'),('Implementation','x'*129),('TC1','NaN'),('TC2','1e999'),('TC1','1k'),('TC1','{x}'),('TC2',True),('Model','X')]:
   with self.subTest(name=name,v=v),self.assertRaises(CadenceError):validate_property_change(name,v)

 def test_snapshot_ignores_traversal_ids_but_preserves_scope_and_all_values(self):
  before=rows();other=copy.deepcopy(before);other.reverse()
  for i,row in enumerate(other):row['partId']=str(i);row['properties'].reverse()
  self.assertEqual(property_snapshot(before),property_snapshot(other))
  other[0]['properties'][0]['value']='CHANGED';self.assertNotEqual(property_snapshot(before),property_snapshot(other))

 def test_expected_change_preserves_same_reference_on_other_schematic(self):
  g=property_snapshot(rows());original=copy.deepcopy(g);e=expected_property_snapshot(g,['ROOT','PAGE','D1'],'Implementation','NEW')
  self.assertEqual(g,original);target=next(r for r in e if r['scope'][0]=='ROOT')
  self.assertEqual(target['properties'],[{'name':'Implementation','value':'NEW'},{'name':'TC1','value':'0'},{'name':'Value','value':'DIODE'}])
  self.assertEqual(next(r for r in e if r['scope'][0]=='AUX'),next(r for r in g if r['scope'][0]=='AUX'))

 def test_missing_ambiguous_and_invalid_snapshot_refused(self):
  g=property_snapshot(rows())
  for graph,scope,name in [(g,['MISSING','PAGE','D1'],'Implementation'),(g+g,['ROOT','PAGE','D1'],'Implementation'),(g,['ROOT','PAGE','D1'],'ABSENT')]:
   with self.assertRaises(CadenceError):expected_property_snapshot(graph,scope,name,'NEW')
  for mode in ('duplicate_id','duplicate_property','unknown_field','nonstring'):
   r=rows()
   if mode=='duplicate_id':r[1]['partId']='p1'
   elif mode=='duplicate_property':r[0]['properties'].append(copy.deepcopy(r[0]['properties'][0]))
   elif mode=='unknown_field':r[0]['unexpected']=True
   else:r[0]['properties'][0]['value']=0
   with self.subTest(mode=mode),self.assertRaises(CadenceError):property_snapshot(r)

 def test_property_text_and_total_budgets(self):
  for name,value in [('X'*257,'ok'),('X','v'*16385)]:
   r=rows();r[0]['properties']=[{'name':name,'value':value}]
   with self.assertRaises(CadenceError):property_snapshot(r)
  r=rows()[:1];r[0]['properties']=[{'name':str(i),'value':'v'*16384} for i in range(512)]
  with self.assertRaises(CadenceError):property_snapshot(r)
  r=rows()[:1];r[0]['properties']=[{'name':str(i),'value':''} for i in range(512)]
  r=[{**copy.deepcopy(r[0]),'partId':str(i)} for i in range(33)]
  with self.assertRaises(CadenceError):property_snapshot(r)
