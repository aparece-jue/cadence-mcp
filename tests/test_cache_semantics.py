import copy,unittest
from cadence_mcp.cache_semantics import effective_property_snapshot
from cadence_mcp.core import CadenceError
class CacheSemanticTests(unittest.TestCase):
    def fixture(self):return {'partId':'p1','schematicName':'S','pageName':'P','reference':'R101','properties':[{'name':'Value','value':'2k'},{'name':'PCB Footprint','value':'KEEP_USER_FP'},{'name':'Source Library','value':'new.olb'}]}
    def test_only_property_enumeration_order_is_ignored_without_mutation(self):
        a=self.fixture();before=copy.deepcopy(a);b=copy.deepcopy(a);b['properties'].reverse()
        self.assertEqual(effective_property_snapshot(a),effective_property_snapshot(b));self.assertEqual(a,before)
    def test_every_value_name_and_qualified_identity_remains_significant(self):
        a=self.fixture()
        for field in ('partId','reference','pageName','schematicName'):
            b=copy.deepcopy(a);b[field]+='x';self.assertNotEqual(effective_property_snapshot(a),effective_property_snapshot(b))
        for i in range(3):
            for field in ('name','value'):
                b=copy.deepcopy(a);b['properties'][i][field]+='x';self.assertNotEqual(effective_property_snapshot(a),effective_property_snapshot(b))
    def test_duplicate_extra_and_invalid_types_are_not_silently_discarded(self):
        a=self.fixture()
        variants=[{**a,'extra':0},{**a,'properties':True},{**a,'properties':a['properties']+[a['properties'][0]]},{**a,'properties':[{'name':'Value','value':False}]},{**a,'properties':[{'name':'Value','value':'2k','extra':0}]}]
        for b in variants:
            with self.assertRaises(CadenceError):effective_property_snapshot(b)
