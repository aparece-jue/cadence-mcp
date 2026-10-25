import copy,unittest
from cadence_mcp.capture_multiunit_place import select_units,existing_definitions
from cadence_mcp.core import CadenceError

def sample():
 data={'package':[{'objectId':'pkg','name':'DUAL'}],'device':[],'cell':[],'part':[],'pin':[]};units=[]
 for i,name in enumerate(('A','B')):
  dev='device-'+name;cell='cell-'+name;part='part-'+name;data['device'].append({'objectId':dev,'packageId':'pkg','position':i,'designator':name});data['cell'].append({'objectId':cell,'name':'CELL'+name});data['part'].append({'objectId':part,'packageId':'pkg','deviceId':dev,'cellId':cell,'name':'PART'+name});pins=[]
  for number,pin_name in [(str(i+1),'SIG'),('8','VCC')]:
   data['pin'].append({'partId':part,'number':number,'name':pin_name});pins.append({'number':number,'name':pin_name,'hotSpot':[100+200*i,200],'connected':False,'net':None})
  units.append({'libraryPartId':part,'location':[100+200*i,200],'rotationCode':0,'mirrorCode':0,'expectedPins':pins})
 return data,units

class MultiunitContractTests(unittest.TestCase):
 def test_shared_physical_number_is_distinct_per_unit(self):
  data,units=sample();package,selected=select_units(data,units);self.assertEqual(package['name'],'DUAL');self.assertEqual([u['deviceDesignator'] for u in selected],['A','B']);self.assertEqual(sum(p['number']=='8' for u in selected for p in u['expectedPins']),2)
 def test_repeating_one_device_cannot_replace_missing_unit(self):
  data,units=sample();units[1]=copy.deepcopy(units[0])
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'invalid_group')
 def test_units_from_different_packages_refused(self):
  data,units=sample();data['part'][1]['packageId']='other'
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'invalid_group')
 def test_missing_hidden_device_not_silently_omitted(self):
  data,units=sample();data['device'].append({'objectId':'power','packageId':'pkg','position':2,'designator':'P'})
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'incomplete_group')
 def test_pin_mapping_cannot_use_other_unit_physical_number(self):
  data,units=sample();units[1]['expectedPins'][0]['number']='1'
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'pin_mapping_mismatch')
 def test_one_physical_shared_pad_cannot_expect_two_power_nets(self):
  data,units=sample();units[0]['expectedPins'][1].update(connected=True,net='VCC');units[1]['expectedPins'][1].update(connected=True,net='GND')
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'shared_pin_binding_conflict')
 def test_unresolved_shared_local_vs_flat_binding_refused(self):
  data,units=sample();units[0]['expectedPins'][1].update(connected=True,net='VCC')
  with self.assertRaises(CadenceError) as got:select_units(data,units)
  self.assertEqual(got.exception.code,'shared_pin_binding_conflict')
 def test_repeated_base_and_shared_numbers_use_pin_identity(self):
  data={'pin':[{'objectId':'a','pageId':'page','reference':'U1','number':'8','connected':False,'net':''},{'objectId':'b','pageId':'page','reference':'U1','number':'8','connected':False,'net':''}]};wanted=existing_definitions(data,'page',[{'pinId':'a','connected':True,'net':'VCC'},{'pinId':'b','connected':False,'net':None}]);self.assertTrue(wanted['pin'][0]['connected']);self.assertFalse(wanted['pin'][1]['connected']);self.assertFalse(data['pin'][0]['connected'])
 def test_missing_existing_shared_pin_cannot_pass_coverage(self):
  data={'pin':[{'objectId':'a','pageId':'page'},{'objectId':'b','pageId':'page'}]}
  with self.assertRaises(CadenceError) as got:existing_definitions(data,'page',[{'pinId':'a','connected':False,'net':None}])
  self.assertEqual(got.exception.code,'incomplete_expectations')

if __name__=='__main__':unittest.main()
