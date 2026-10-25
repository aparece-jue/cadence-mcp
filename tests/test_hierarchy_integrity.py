import copy
import unittest
from cadence_mcp.capture_hierarchy import validate_hierarchy
from cadence_mcp.core import CadenceError

def tree():
    return [dict(occurrenceId='root',parentId=None,depth=0,path='/',hierarchicalPath='/',reference='',properties=[]),
            dict(occurrenceId='child',parentId='root',depth=1,path='/U1',hierarchicalPath='/U1',reference='U1',properties=[])]

class HierarchyTextIntegrityTests(unittest.TestCase):
    def test_identity_fields_are_bounded(self):
        for key,limit in [('occurrenceId',256),('path',16384),('hierarchicalPath',16384),('reference',256)]:
            rows=tree();rows[1][key]='x'*(limit+1)
            with self.subTest(key=key),self.assertRaises(CadenceError):validate_hierarchy(rows)

    def test_properties_have_individual_limits(self):
        for name,value in [('x'*257,''),('Value','x'*16385)]:
            rows=tree();rows[1]['properties']=[{'name':name,'value':value}]
            with self.subTest(nameLength=len(name)),self.assertRaises(CadenceError):validate_hierarchy(rows)

    def test_utf8_total_budget_counts_bytes_not_characters(self):
        rows=tree();rows[1]['properties']=[{'name':str(i),'value':'中'*16384} for i in range(171)]
        with self.assertRaises(CadenceError):validate_hierarchy(rows)

    def test_literal_unicode_empty_value_and_max_lengths_accepted_unchanged(self):
        rows=tree();rows[1]['properties']=[{'name':'x'*256,'value':'中'*16384},{'name':'literal[x]$;','value':''}]
        before=copy.deepcopy(rows);validate_hierarchy(rows);self.assertEqual(rows,before)

    def test_invalid_utf8_surrogate_is_structured_failure(self):
        rows=tree();rows[1]['properties']=[{'name':'Value','value':'\ud800'}]
        with self.assertRaises(CadenceError) as error:validate_hierarchy(rows)
        self.assertEqual(error.exception.code,'invalid_worker_result')
