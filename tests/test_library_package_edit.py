import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_vector_edit import vector_graph
from cadence_mcp.library_package_edit import expected_package_edit,validate_package_properties,query_package_properties
from test_library_vector_edit import inspection

def package(name='TEST'):
    return {'packageName':name,'referenceTemplate':'U?','footprint':'FP','pcbLibrary':'LIB','designator':'U?',
            'userPropsPermitted':1,'userProperties':[]}
def graph():return {'library':vector_graph(inspection()),'packageProperties':[package()]}
def prop(name,value):return {'name':name,'value':value,'nativeType':0,'editable':1,'deletable':1}

class PackageEditTests(unittest.TestCase):
    def test_native_user_strings_preserve_numeric_boolean_and_empty_literals(self):
        values=['00123','1e3','False','','器件 00123']
        users=[{'name':'LITERAL_'+str(i),'operation':'set','value':value} for i,value in enumerate(values)]
        expected=expected_package_edit(graph(),'TEST',{},users)[0]
        props=expected['packageProperties'][0]['userProperties']
        self.assertEqual([p['value'] for p in props],values)
        self.assertTrue(all(p['nativeType']==0 for p in props))

    def test_non_string_user_values_not_silently_coerced(self):
        for value in (123,False,1.5,[],{},None):
            with self.subTest(value=value),self.assertRaises(CadenceError):
                expected_package_edit(graph(),'TEST',{},[{'name':'P','operation':'set','value':value}])

    def test_fixed_fields_update_both_independent_getter_views_and_preserve_symbols(self):
        source=graph();before=copy.deepcopy(source)
        expected,fields,operations,old=expected_package_edit(source,'TEST',{'referenceTemplate':'J?','footprint':'NEW_FP','pcbLibrary':'NEW_LIB'},[])
        self.assertEqual(source,before);self.assertFalse(operations)
        self.assertEqual(expected['library']['metadata']['symbols'],source['library']['metadata']['symbols'])
        self.assertEqual(expected['library']['definitions']['pin'],source['library']['definitions']['pin'])
        self.assertEqual(expected['library']['definitions']['package'][0]['footprint'],'NEW_FP')
        self.assertEqual(expected['library']['metadata']['packages'][0]['referenceTemplate'],'J?')
        self.assertEqual(expected['packageProperties'][0]['designator'],'J?')
    def test_explicit_empty_value_is_present_until_separate_deletion(self):
        source=graph()
        created,_,ops,_=expected_package_edit(source,'TEST',{},[{'name':'标签$[x];','operation':'set','value':'value\nΩ'}])
        self.assertIsNone(ops[0]['old'])
        empty,_,_,_=expected_package_edit(created,'TEST',{},[{'name':'标签$[x];','operation':'set','value':''}])
        self.assertEqual(empty['packageProperties'][0]['userProperties'],[prop('标签$[x];','')])
        deleted,_,_,_=expected_package_edit(empty,'TEST',{},[{'name':'标签$[x];','operation':'delete','value':None}])
        self.assertEqual(deleted['packageProperties'][0]['userProperties'],[])
        self.assertEqual(source,graph())
    def test_reserved_names_duplicates_and_existing_case_alias_refused(self):
        source=graph();source['packageProperties'][0]['userProperties']=[prop('MPN','A')]
        changes=[[{'name':'PCB Footprint','operation':'set','value':'x'}],
                 [{'name':'A','operation':'set','value':'x'},{'name':'a','operation':'set','value':'y'}],
                 [{'name':'mpn','operation':'set','value':'B'}]]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(CadenceError):expected_package_edit(source,'TEST',{},change)
    def test_locked_typed_undeletable_and_disallowed_creation_refused(self):
        for patch_row,op in [({'nativeType':1},'set'),({'editable':0},'set'),({'deletable':0},'delete')]:
            source=graph();source['packageProperties'][0]['userProperties']=[{**prop('P','old'),**patch_row}]
            with self.assertRaises(CadenceError):expected_package_edit(source,'TEST',{},[{'name':'P','operation':op,'value':'new' if op=='set' else None}])
        source=graph();source['packageProperties'][0]['userPropsPermitted']=0
        with self.assertRaises(CadenceError):expected_package_edit(source,'TEST',{},[{'name':'P','operation':'set','value':'new'}])
    def test_noop_missing_delete_and_invalid_builtin_fields_refused(self):
        source=graph()
        for changes,users in [({},[]),({'footprint':'FP'},[]),({'referenceTemplate':'U;exit'},[]),({'footprint':'bad\nname'},[]),
                              ({'method':'eval'},[]),({},[{'name':'MISSING','operation':'delete','value':None}]),
                              ({},[{'name':'P','operation':'set','value':None}])]:
            with self.subTest(changes=changes,users=users),self.assertRaises(CadenceError):expected_package_edit(source,'TEST',changes,users)
    def test_distinct_native_template_designator_semantics_are_not_guessed(self):
        source=graph();source['packageProperties'][0]['designator']='OTHER'
        with self.assertRaises(CadenceError) as caught:expected_package_edit(source,'TEST',{'referenceTemplate':'J?'},[])
        self.assertEqual(caught.exception.code,'package_designator_semantics')
    def test_other_package_explicit_metadata_is_preserved(self):
        source=graph();other=package('OTHER');other['userProperties']=[prop('KEEP','unchanged')];source['packageProperties'].append(other)
        expected,_,_,_=expected_package_edit(source,'TEST',{'footprint':''},[{'name':'NEW','operation':'set','value':'N'}])
        self.assertEqual(expected['packageProperties'][1],other)
        self.assertEqual(source['packageProperties'][0]['userProperties'],[])
    def test_clearing_footprint_recanonicalizes_package_rows_after_semantic_edit(self):
        source=graph();other=package('OTHER');other['footprint']='ZZZ';source['packageProperties'].append(other)
        source['library']['definitions']['package'].append({'name':'OTHER','size':1,'homogeneous':True,'footprint':'ZZZ'})
        expected,_,_,_=expected_package_edit(source,'OTHER',{'footprint':''},[])
        self.assertEqual([r['name'] for r in expected['library']['definitions']['package']],['OTHER','TEST'])
        self.assertEqual(source['library']['definitions']['package'][1]['footprint'],'ZZZ')
    def test_malformed_native_property_types_flags_and_case_collisions_rejected(self):
        for mutation in [lambda r:r.update(userPropsPermitted=True),lambda r:r.update(userProperties=[prop('A','1'),prop('a','2')]),
                         lambda r:r.update(userProperties=[{**prop('A','1'),'nativeType':True}]),
                         lambda r:r.update(userProperties=[{**prop('A','1'),'editable':2}])]:
            row=package();mutation(row)
            with self.assertRaises(CadenceError):validate_package_properties([row])
    def test_cached_properties_are_still_source_hash_bound_and_wrong_owner_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
            work=root/'work';directory=work/'lib';directory.mkdir(parents=True);source=directory/'library.olb';source.write_bytes(b'owned')
            library=LibraryService(Config(install,work,(root,)))
            library.sessions['lib']={'directory':directory,'revision':sha256(source),'data':{'package':[{'objectId':'p','name':'TEST'}]},'packageProperties':[package()]}
            row=query_package_properties(library,'lib','p');self.assertEqual(row['properties'],package());row['properties']['footprint']='mutated response'
            self.assertEqual(query_package_properties(library,'lib','p')['properties']['footprint'],'FP')
            with self.assertRaises(CadenceError):query_package_properties(library,'lib','foreign')
            source.write_bytes(b'tampered')
            with self.assertRaises(CadenceError) as caught:query_package_properties(library,'lib','p')
            self.assertEqual(caught.exception.code,'target_changed')
