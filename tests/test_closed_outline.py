import unittest
from cadence_mcp.closed_outline import simple_ring,strictly_inside,segment_inside
from cadence_mcp.capture_symbol_contacts import analyze_symbol_contacts
from cadence_mcp.core import CadenceError
from test_symbol_contacts import vector,wire
BOX=[[0,0],[10,0],[10,10],[0,10]]
class ClosedOutlineTests(unittest.TestCase):
 def test_strict_inside_edges_and_orientation(self):
  for ring in (BOX,list(reversed(BOX))):
   self.assertTrue(strictly_inside([5,5],ring));self.assertFalse(strictly_inside([0,5],ring));self.assertFalse(strictly_inside([11,5],ring));self.assertFalse(strictly_inside([0,0],ring))
 def test_strict_segment_and_boundary_touch(self):
  self.assertTrue(segment_inside([1,2],[9,8],BOX));self.assertFalse(segment_inside([0,2],[9,8],BOX));self.assertFalse(segment_inside([1,2],[1,2],BOX))
 def test_concave_exit_not_accepted_from_endpoints(self):
  ring=[[0,0],[10,0],[10,10],[7,10],[7,3],[3,3],[3,10],[0,10]]
  self.assertIsNotNone(simple_ring(ring));self.assertTrue(strictly_inside([1,8],ring));self.assertTrue(strictly_inside([9,8],ring));self.assertFalse(segment_inside([1,8],[9,8],ring));self.assertTrue(segment_inside([1,1],[9,1],ring))
 def test_self_touch_crossing_zero_area_and_backtracking_rejected(self):
  for points in ([[0,0],[10,10],[0,10],[10,0]],[[0,0],[10,0],[5,0]],[[0,0],[10,0],[5,0],[10,10],[0,10]],[[0,0],[10,0],[10,10],[5,0],[0,10]]):self.assertIsNone(simple_ring(points))
 def test_closing_repeat_and_consecutive_repeat_normalized(self):self.assertEqual(simple_ring(BOX+[BOX[0]]),BOX);self.assertEqual(simple_ring([BOX[0]]+BOX),BOX)
 def test_large_integer_precision(self):
  n=2147483600;ring=[[n,n],[n+10,n],[n+10,n+10],[n,n+10]];self.assertTrue(segment_inside([n+1,n+2],[n+9,n+8],ring))
 def test_report_containment_separate_from_boundary_and_not_pass(self):
  result=analyze_symbol_contacts([vector(BOX,'box')],[wire([[1,2],[9,8]])],'part','page');self.assertEqual(result['countsByContactKind'],{'contained_segment':1});self.assertIsNone(result['findings'][0]['vectorSegmentIndex']);self.assertIsNone(result['designPassed']);self.assertFalse(result['renderedClearanceVerified'])
 def test_non_simple_skip_keeps_boundary_candidates(self):
  result=analyze_symbol_contacts([vector([[0,0],[10,10],[0,10],[10,0]],'polygon')],[wire([[5,-5],[5,15]])],'part','page');self.assertFalse(result['simpleClosedContainmentCoverageComplete']);self.assertEqual(len(result['skippedContainmentOutlines']),1);self.assertTrue(result['findings'])
 def test_simplicity_budget_refused(self):
  with self.assertRaises(CadenceError):simple_ring([[x,x*x] for x in range(1001)])
