import unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.wiring import analyze_wiring
from test_wiring import data

class ExactWiringTests(unittest.TestCase):
    def test_non_integer_diagonal_crossing_is_exact_not_rounded(self):
        report=analyze_wiring(data([[0,0],[3,3]],[[0,2],[3,0]]))
        row=next(f for f in report['findings'] if f['ruleId']=='WIRE-CROSSING-CANDIDATE')
        self.assertIsNone(row['point']);self.assertEqual(row['pointExact'],[{'numerator':6,'denominator':5}]*2)
        self.assertEqual(row['electricalConnection'],'not_evaluated');self.assertTrue(report['geometryComplete'])
    def test_diagonal_reverse_overlap_and_t_contact(self):
        report=analyze_wiring(data([[10,10],[0,0]],[[5,5],[15,15]]))
        row=next(f for f in report['findings'] if f['ruleId']=='WIRE-COLLINEAR-OVERLAP')
        self.assertEqual((row['start'],row['end']),([5,5],[10,10]))
        report=analyze_wiring(data([[0,0],[10,10]],[[5,5],[8,2]]))
        self.assertEqual(report['countsByRule']['WIRE-T-CONTACT-CANDIDATE'],1)
        shared=analyze_wiring(data([[0,0],[10,10]],[[10,10],[12,8]]))
        self.assertNotIn('WIRE-CROSSING-CANDIDATE',shared['countsByRule'])
    def test_grid_origin_negative_coordinates_and_optional_coverage(self):
        doc=data([[-5,-5],[15,-5]])
        self.assertNotIn('WIRE-OFF-GRID-VERTEX',analyze_wiring(doc,10,[5,5])['countsByRule'])
        self.assertEqual(analyze_wiring(doc,10,[0,0])['countsByRule']['WIRE-OFF-GRID-VERTEX'],2)
        self.assertIn('grid_alignment',analyze_wiring(doc)['notChecked'])
        self.assertNotIn('grid_alignment',analyze_wiring(doc,10)['notChecked'])
    def test_grid_booleans_bounds_and_origin_without_size_refused(self):
        for size,origin in ((True,None),(0,None),(1000001,None),(None,[0,0]),(10,[True,0]),(10,[0]),(10,[0,1.5])):
            with self.assertRaises(CadenceError):analyze_wiring(data([[0,0],[1,0]]),size,origin)
    def test_zero_length_and_grid_findings_remain_bounded(self):
        with self.assertRaises(CadenceError) as error:analyze_wiring(data([[1,1]]*10000),10)
        self.assertEqual(error.exception.code,'geometry_limit')
    def test_large_native_coordinates_exact_and_outside_native_range_refused(self):
        n=2147483647
        report=analyze_wiring(data([[-n,-n],[n,n]],[[-n,n],[n,-n]]))
        row=next(f for f in report['findings'] if f['ruleId']=='WIRE-CROSSING-CANDIDATE')
        self.assertEqual(row['point'],[0,0])
        with self.assertRaises(CadenceError):analyze_wiring(data([[0,0],[n+1,0]]))
