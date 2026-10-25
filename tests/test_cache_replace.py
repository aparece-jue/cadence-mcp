import copy,unittest
from cadence_mcp.capture_cache_replace import expected_replacement,normalize_state,cache_groups,NEW_LIBRARY
from cadence_mcp.core import CadenceError
from test_library import document

def fixture():
 lib=document();data={'schematic':[{'objectId':'s','name':'ROOT'}],'page':[{'objectId':'p','schematicId':'s','name':'PAGE'}],'part':[],'pin':[]};units={};raw=[];bindings=[];declarations=[]
 for i in (1,2):
  pid=f'i{i}';ref=f'R10{i}';data['part'].append({'objectId':pid,'schematicId':'s','pageId':'p','reference':ref})
  data['pin'].append({'objectId':pid+'/pin','partId':pid,'schematicId':'s','pageId':'p','reference':ref,'number':'11','name':'OLD','connected':True,'net':'N'+str(i)})
  units[pid]={'partId':pid,'nativeId':i,'schematicName':'ROOT','pageName':'PAGE','reference':ref,'kind':'placed','isExternalDesignPart':False,'packageName':'OLD','packageSize':1,'deviceDesignator':'A','referenceDesignator':ref,'sourceLib':'C:/old.olb','sourcePart':'OLD.Normal'}
  raw.append({'partId':pid,'nativeId':i,'schematicName':'ROOT','pageName':'PAGE','reference':ref,
   'geometry':{'physicalPinNumbersApplicable':True,'location':[10*i,20],'rotationCode':0,'mirrorCode':0,'pins':[{'numberState':0,'number':'11','name':'OLD','hotSpot':[10*i,20]}]},
   'effective':[{'name':k,'value':v} for k,v in {'Value':'1k','PCB Footprint':'USER_FP','Source Library':'C:/old.olb','Source Package':'OLD','Source Part':'OLD.Normal','Graphic':'OLD.Normal'}.items()],
   'user':[{'name':'NOTE','value':'literal [x]$;','nativeType':0,'editable':1,'deletable':1}],
   'display':[{'name':'Value','value':'1k','location':[5,10],'rotationCode':0,'displayTypeCode':1,'colorCode':0}]})
  bindings.append({'partId':pid,'cachePackageId':'cache-old','isCached':True,'lookupMatchesPlaced':True,'originVerified':True})
  declarations.append({'partId':pid,'libraryPartId':'part1','pins':[{'number':'11','name':'端子','hotSpot':[10*i,20],'connected':True,'net':'N'+str(i)}]})
 return data,units,{'bindings':bindings},bindings[0],lib,declarations,normalize_state(raw,units),raw

def expected(args):
 data,units,q,b,lib,d,state,_=args;return expected_replacement(data,units,q,b,lib,'p1',d,state)

class CacheReplacementTests(unittest.TestCase):
 def test_all_bound_instances_and_layers_preserved_with_explicit_changes(self):
  args=fixture();old=copy.deepcopy(args);pkg,changes,data,state,units=expected(args)
  self.assertEqual(len(changes),2);self.assertEqual(pkg['name'],'R1');self.assertEqual(args,old)
  for row in data['pin']:self.assertEqual(row['name'],'端子');self.assertEqual(row['net'],'N'+row['partId'][-1])
  for before,after in zip(args[6],state):
   self.assertEqual(before['user'],after['user']);self.assertEqual(before['display'],after['display'])
   self.assertEqual(next(p['value'] for p in after['effective'] if p['name']=='Source Library'),NEW_LIBRARY)
  self.assertTrue(all(u['sourceLib']==NEW_LIBRARY and u['packageName']=='R1' for u in units.values()))
 def test_exact_affected_group_coverage(self):
  for mode in ('missing','duplicate','foreign'):
   args=list(fixture())
   if mode=='missing':args[5].pop()
   elif mode=='duplicate':args[5][1]=copy.deepcopy(args[5][0])
   else:args[5][0]['partId']='foreign'
   with self.subTest(mode=mode),self.assertRaises(CadenceError):expected(args)
 def test_pin_net_pad_and_hotspot_changes_refused(self):
  for mode in ('net','number','name','hotspot','missing'):
   args=list(fixture());p=args[5][0]['pins'][0]
   if mode=='net':p['net']='SHORT'
   elif mode=='number':p['number']='99'
   elif mode=='name':p['name']='wrong'
   elif mode=='hotspot':p['hotSpot']=[999,0]
   else:args[5][0]['pins']=[]
   with self.subTest(mode=mode),self.assertRaises(CadenceError):expected(args)
 def test_package_device_external_and_view_preconditions(self):
  for mode in ('size','device','external','view'):
   args=list(fixture())
   if mode=='size':args[4]['package'][0]['size']=2
   elif mode=='device':args[4]['device'][0]['designator']='B'
   elif mode=='external':args[1]['i1']['isExternalDesignPart']=True
   else:args[5][0]['libraryPartId']='foreign'
   with self.subTest(mode=mode),self.assertRaises(CadenceError):expected(args)
 def test_typed_or_source_binding_override_refused(self):
  for change in ({'nativeType':2},{'name':'Source Library'}):
   args=list(fixture());args[6][0]['user'][0].update(change)
   with self.subTest(change=change),self.assertRaises(CadenceError):expected(args)
 def test_full_state_coverage_native_id_and_property_flags(self):
  for mode in ('missing','native','duplicate','property_type','display'):
   args=list(fixture());raw=args[7]
   if mode=='missing':raw.pop()
   elif mode=='native':raw[0]['nativeId']=10
   elif mode=='duplicate':raw[1]['nativeId']=raw[0]['nativeId']
   elif mode=='property_type':raw[0]['user'][0]['editable']=True
   else:raw[0]['display'][0]['location']=[True,0]
   with self.subTest(mode=mode),self.assertRaises(CadenceError):normalize_state(raw,args[1])
 def test_drawn_missing_physical_number_explicitly_not_applicable(self):
  args=list(fixture());raw=args[7];units=args[1];units['i1']['kind']='drawn';g=raw[0]['geometry'];g['physicalPinNumbersApplicable']=False;g['pins'][0].update(number='',numberState=1021)
  normalize_state(raw,units)
  units['i1']['kind']='placed';g['physicalPinNumbersApplicable']=True
  with self.assertRaises(CadenceError):normalize_state(raw,units)
 def test_same_name_cache_groups_keep_source_and_local_kind(self):
  lib=document();lib['package'][1]['name']=lib['package'][0]['name']
  q={'definitions':lib,'origins':[{'cachePackageId':'p1','isCached':True,'sourceLibrary':'C:/old.olb'}, {'cachePackageId':'p2','isCached':False,'sourceLibrary':''}]}
  groups=cache_groups(q);self.assertEqual(len(groups),2);self.assertEqual({r['isCached'] for r in groups},{True,False})
