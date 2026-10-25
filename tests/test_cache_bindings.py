import copy,unittest
from cadence_mcp.capture_cache_bindings import validate_cache_bindings
from cadence_mcp.core import CadenceError
from test_library import document

def fixture():
 data=document()
 # Same package name and even identical source cell/view names are permitted as separate cache entries.
 data['package'][1]['name']=data['package'][0]['name']
 design={'schematic':[{'objectId':'s','name':'ROOT'}],'page':[{'objectId':'p','schematicId':'s','name':'PAGE'}],
         'part':[{'objectId':'i1','schematicId':'s','pageId':'p','reference':'R1'}],'pin':[]}
 origins=[{'cachePackageId':'p1','isCached':True,'sourceLibrary':'C:/old/source.olb','originVerified':True},
          {'cachePackageId':'p2','isCached':False,'sourceLibrary':'','originVerified':False}]
 bindings=[{'partId':'i1','nativeId':20,'schematicName':'ROOT','pageName':'PAGE','reference':'R1','cachePackageId':'p1',
            'sourceLibrary':'C:/old/source.olb','sourcePackage':'R1','sourcePart':'R','deviceDesignator':'A',
            'isCached':True,'lookupMatchesPlaced':True,'originVerified':True}]
 units={'i1':{'kind':'placed','nativeId':20,'sourceLib':'C:/old/source.olb','sourcePart':'R','deviceDesignator':'A','packageName':'R1'}}
 return {'definitions':data,'origins':origins,'bindings':bindings},design,units

class CacheBindingTests(unittest.TestCase):
 def test_same_name_local_and_cache_remain_distinct_and_snapshot_detached(self):
  s,d,u=fixture();v=validate_cache_bindings(s,d,u)
  self.assertEqual(v,s);self.assertEqual(v['bindings'][0]['cachePackageId'],'p1')
  v['origins'][0]['sourceLibrary']='changed';self.assertEqual(s['origins'][0]['sourceLibrary'],'C:/old/source.olb')
 def test_wrong_source_local_package_and_scope_refused(self):
  for mode in ('source','local','scope','native_id','view','device'):
   s,d,u=fixture();b=s['bindings'][0]
   if mode=='source':b['sourceLibrary']='C:/other/source.olb'
   elif mode=='local':b['cachePackageId']='p2'
   elif mode=='scope':b['schematicName']='AUX'
   elif mode=='native_id':b['nativeId']=21
   elif mode=='view':b['sourcePart']='OTHER'
   else:b['deviceDesignator']='B'
   with self.subTest(mode=mode),self.assertRaises(CadenceError):validate_cache_bindings(s,d,u)
 def test_missing_duplicate_origins_and_missing_binding_refused(self):
  for mode in ('missing_origin','duplicate_origin','missing_binding','duplicate_binding','unknown_binding','missing_unit'):
   s,d,u=fixture()
   if mode=='missing_origin':s['origins'].pop()
   elif mode=='duplicate_origin':s['origins'][1]=copy.deepcopy(s['origins'][0])
   elif mode=='missing_binding':s['bindings']=[]
   elif mode=='duplicate_binding':s['bindings'].append(copy.deepcopy(s['bindings'][0]))
   elif mode=='unknown_binding':s['bindings'][0]['partId']='foreign'
   else:u={}
   with self.subTest(mode=mode),self.assertRaises(CadenceError):validate_cache_bindings(s,d,u)
 def test_cached_origin_must_be_verified_and_flags_strict(self):
  for key,value in [('originVerified',False),('isCached',1),('sourceLibrary','')]:
   s,d,u=fixture();s['origins'][0][key]=value
   with self.subTest(key=key),self.assertRaises(CadenceError):validate_cache_bindings(s,d,u)
 def test_source_case_variation_accepted_but_not_other_native_identity(self):
  s,d,u=fixture();s['bindings'][0]['sourceLibrary']='c:/OLD/SOURCE.OLB';validate_cache_bindings(s,d,u)
  u['i1']['kind']='drawn'
  with self.assertRaises(CadenceError):validate_cache_bindings(s,d,u)
