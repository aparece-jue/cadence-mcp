import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.hierarchy_semantics import net_partition,verify_reused_context,native_partition_rows
def pin(context,part,name,number,flat,netname,glob=False):return {'instancePathSegments':[context,part],'name':name,'occurrencePhysicalNumber':number,'flatNetId':flat,'flatNetName':netname,'isGlobal':glob if flat else None}
class HierarchySemanticTests(unittest.TestCase):
    def test_native_flags_decode_only_zero_one_and_keep_input_intact(self):
        rows=[pin('A','U1A','I','1','n1','X')];rows[0]['isGlobal']=0
        self.assertIs(native_partition_rows(rows)[0]['isGlobal'],False);self.assertIs(type(rows[0]['isGlobal']),int)
        rows[0]['isGlobal']=2
        with self.assertRaises(CadenceError):native_partition_rows(rows)
    def fixture(self):
        old=[pin('A','U1A','I','1','n1','A/X'),pin('A','U1A','O','2','n2','A/Y'),pin('A','U1A','VCC','14','g','VCC',True),pin('B','U1A','I','1','n3','B/X')]
        new=old+[pin('C','U1A','I','1','n4','C/X'),pin('C','U1A','O','2','n5','C/Y'),pin('C','U1A','VCC','14','g','VCC',True)]
        return old,new
    def test_partition_ignores_snapshot_ids_and_row_order_only(self):
        old,_=self.fixture();other=copy.deepcopy(old)
        for p in other:p['flatNetId']='copy-'+p['flatNetId']
        other.reverse();self.assertEqual(net_partition(old),net_partition(other))
        other[0]['flatNetName']='renamed';self.assertNotEqual(net_partition(old),net_partition(other))
    def test_copied_private_names_differ_but_native_objects_are_isolated(self):
        old,new=self.fixture();before=copy.deepcopy(new);result=verify_reused_context(old,new,'A','C',{'VCC','GND'})
        self.assertTrue(result['privateNetsIsolated']);self.assertEqual(result['sharedGlobalNames'],['VCC']);self.assertEqual(new,before)
    def test_private_merge_and_clone_short_are_rejected(self):
        old,new=self.fixture();bad=copy.deepcopy(new);bad[-3]['flatNetId']='n1';bad[-3]['flatNetName']='A/X'
        with self.assertRaises(CadenceError):verify_reused_context(old,bad,'A','C',{'VCC'})
        bad=copy.deepcopy(new);bad[-2]['flatNetId']='n4';bad[-2]['flatNetName']='C/X'
        with self.assertRaises(CadenceError):verify_reused_context(old,bad,'A','C',{'VCC'})
    def test_duplicate_physical_pins_invalid_global_and_missing_fields_refused(self):
        old,new=self.fixture()
        for rows in (old+[old[0]], [{**old[0],'isGlobal':1}], [{**old[0],'flatNetId':None}], [{k:v for k,v in old[0].items() if k!='occurrencePhysicalNumber'}]):
            with self.assertRaises(CadenceError):net_partition(rows)
    def test_original_disconnect_physical_remap_and_unapproved_global_rejected(self):
        old,new=self.fixture()
        for mutation in ({'occurrencePhysicalNumber':'99'},{'flatNetId':None,'flatNetName':'','isGlobal':None}):
            bad=copy.deepcopy(new);bad[0].update(mutation)
            with self.assertRaises(CadenceError):verify_reused_context(old,bad,'A','C',{'VCC'})
        with self.assertRaises(CadenceError):verify_reused_context(old,new,'A','C',{'GND'})
