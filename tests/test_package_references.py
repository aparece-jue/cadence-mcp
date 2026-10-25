import copy
import unittest
from cadence_mcp.capture_package_references import package_reference_map,rename_state_and_units,nc_owner_graph,node_reference_table
from cadence_mcp.core import CadenceError


def fixture():
    data={'schematic':[{'objectId':'s','name':'ROOT'}],'part':[],'pin':[]}
    units={};bindings=[]
    for index,(key,ref,suffix,page) in enumerate((('a','U1','A','P1'),('b','U1','B','P2'),('c','U10','A','P1'),('d','U10','B','P1'))):
        data['part'].append({'objectId':key,'schematicId':'s','pageId':page,'reference':ref})
        units[key]={'partId':key,'nativeId':index+1,'schematicName':'ROOT','pageName':page,'reference':ref,'referenceDesignator':ref+suffix,'kind':'placed','isExternalDesignPart':False,'packageSize':2,'packageName':'DUAL','deviceDesignator':suffix,'sourceLib':'source.olb','sourcePart':'NORMAL'}
        bindings.append({'partId':key,'cachePackageId':'cache','isCached':True,'lookupMatchesPlaced':True,'originVerified':True})
        for number,name,net in (('1' if suffix=='A' else '2','IN',''),('8','VCC','VCC')):
            data['pin'].append({'objectId':key+number,'partId':key,'reference':ref,'number':number,'name':name,'connected':bool(net),'net':net})
    return data,units,bindings


class PackageReferenceTests(unittest.TestCase):
    def test_expand_cross_page_without_prefix_substitution(self):
        d,u,b=fixture();before=copy.deepcopy((d,u,b));changes,expected=package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])
        self.assertEqual({c['partId'] for c in changes},{'a','b'})
        self.assertEqual([p['reference'] for p in expected['part']],['U2','U2','U10','U10'])
        self.assertEqual((d,u,b),before)
        self.assertEqual({c['temporaryReference'] for c in changes},{'U900000000'})

    def test_swap_whole_packages_and_reserve_unit_alias(self):
        d,u,b=fixture();u['extra']={**u['a'],'partId':'extra','reference':'X1','referenceDesignator':'U900000000A'}
        d['part'].append({'objectId':'extra','schematicId':'s','pageId':'P1','reference':'X1'})
        changes,_=package_reference_map(d,u,b,[{'partId':'a','newReference':'U10'},{'partId':'c','newReference':'U1'}])
        self.assertEqual([c['newFullReference'] for c in changes],['U10A','U10B','U1A','U1B'])
        self.assertEqual([c['temporaryReference'] for c in changes],['U900000001','U900000001','U900000002','U900000002'])

    def test_unmapped_base_and_full_alias_collisions(self):
        for destination in ('U10','u10'):
            with self.assertRaises(CadenceError):package_reference_map(*fixture(),[{'partId':'a','newReference':destination}])
        d,u,b=fixture();u['c']['referenceDesignator']='U2A'
        with self.assertRaises(CadenceError):package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])

    def test_duplicate_group_and_conflicting_destinations(self):
        for mappings in ([{'partId':'a','newReference':'U2'},{'partId':'b','newReference':'U3'}],[{'partId':'a','newReference':'U2'},{'partId':'c','newReference':'u2'}]):
            with self.assertRaises(CadenceError):package_reference_map(*fixture(),mappings)

    def test_unverified_or_inconsistent_package_ownership(self):
        for kind in ('cache','device','external','full','verified'):
            d,u,b=fixture()
            if kind=='cache':b[1]['cachePackageId']='other'
            if kind=='device':u['b']['deviceDesignator']='A';u['b']['referenceDesignator']='U1A'
            if kind=='external':u['b']['isExternalDesignPart']=True
            if kind=='full':u['b']['referenceDesignator']='U1C'
            if kind=='verified':b[1]['originVerified']=False
            with self.subTest(kind=kind),self.assertRaises(CadenceError):package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])

    def test_shared_physical_pad_conflict_is_not_hidden(self):
        d,u,b=fixture();d['pin'][3]['net']='OTHER'
        with self.assertRaises(CadenceError) as error:package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])
        self.assertEqual(error.exception.code,'shared_pin_binding_conflict')

    def test_group_scope_does_not_merge_other_schematic(self):
        d,u,b=fixture();d['part'][1]['schematicId']='other';u['b']['schematicName']='OTHER'
        changes,_=package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])
        self.assertEqual([c['partId'] for c in changes],['a'])

    def test_exact_reference_properties_and_free_text_preserved(self):
        d,u,b=fixture();changes,_=package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}])
        state=[{'nativeId':1,'reference':'U1','geometry':{'location':[10,20]},'effective':[{'name':'Reference','value':'U1'},{'name':'Part Reference','value':'U1A'},{'name':'NOTE','value':'U1 / U10'}],'user':[],'display':[{'name':'Part Reference','value':'','location':[7,8]}]}]
        before=copy.deepcopy(state);renamed,nu=rename_state_and_units(state,u,changes)
        self.assertEqual([p['value'] for p in renamed[0]['effective']],['U2','U2A','U1 / U10'])
        self.assertEqual(renamed[0]['geometry'],state[0]['geometry']);self.assertEqual(renamed[0]['display'],state[0]['display'])
        self.assertEqual(nu['b']['referenceDesignator'],'U2B');self.assertEqual(state,before)
        state[0]['effective'][0]['value']='prefix U1'
        with self.assertRaises(CadenceError):rename_state_and_units(state,u,changes)

    def test_nc_owner_and_old_new_nodes_survive_rename(self):
        d,u,b=fixture();changes,expected=package_reference_map(d,u,b,[{'partId':'a','newReference':'U2'}]);_,nu=rename_state_and_units([],u,changes)
        objects=[{'kind':'nc','attributes':{'partId':'a','pinId':'a1','number':'1','reference':'U1','hotSpot':[10,20]}}]
        before=nc_owner_graph(d,objects,u);objects[0]['attributes']['reference']='U2'
        self.assertEqual(before,nc_owner_graph(expected,objects,nu))
        table=node_reference_table(d,u,changes);self.assertEqual(table,node_reference_table(expected,nu,changes,after=True))
        self.assertEqual(len(table),4);self.assertEqual(table[0]['oldFullReference'],'U1A');self.assertEqual(table[0]['newFullReference'],'U2A')
        objects[0]['attributes']['partId']='b'
        with self.assertRaises(CadenceError):nc_owner_graph(expected,objects,nu)

    def test_invalid_input_and_unnumbered_rejected(self):
        for mapping in ([],[{'partId':'missing','newReference':'U2'}],[{'partId':'a','newReference':'U?'}],[{'partId':'a','newReference':'R2'}],[{'partId':'a','newReference':'U2','eval':'x'}]):
            with self.assertRaises(CadenceError):package_reference_map(*fixture(),mapping)
