import copy,unittest
from cadence_mcp.capture_page_bounds import validate_dimensions,classify_control_points
from cadence_mcp.core import CadenceError
RAW={'sizeName':'A','pageWidth':9700,'pageHeight':7200,'pinToPin':100,'isMetric':0,'size':[9700,7200],'docUnits':[970,720],'drawableDocUnits':[950,700],'docUnitsPerInch':100.0,'physicalGranularity':100.0,'pinToPinScaleFactor':1.0,'borderDisplayed':1,'borderPrinted':1,'gridRefDisplayed':1,'gridRefPrinted':1,'titleBlockDisplayed':1,'titleBlockPrinted':1,'ansiGridRefs':1,'outerBorderMargin':[0,0],'innerBorderMargin':[100,100]}
def row(points,kind='line'):return {'objectId':'p/graphic-1','kind':kind,'pageControlPoints':points}
class PageBoundsTests(unittest.TestCase):
 def test_native_dimensions_remain_distinct_from_document_units(self):
  out=validate_dimensions(RAW);self.assertEqual(out['pageWidth'],9700);self.assertEqual(out['docUnits'],[970,720]);out['docUnits'][0]=0;self.assertEqual(RAW['docUnits'][0],970)
 def test_zero_size_is_retained_for_explicit_unknown_not_invented(self):
  raw=copy.deepcopy(RAW);raw.update(pageWidth=0,pageHeight=0,size=[0,0],docUnits=[0,0],drawableDocUnits=[-20,-20]);self.assertEqual(validate_dimensions(raw)['docUnits'],[0,0])
 def test_rejects_nonfinite_wrong_types_and_extra_fields(self):
  for change in ({'docUnitsPerInch':float('nan')},{'physicalGranularity':0},{'isMetric':True},{'pageWidth':True},{'pinToPin':0},{'docUnits':[-1,720]},{'extra':1}):
   with self.assertRaises(CadenceError):validate_dimensions({**copy.deepcopy(RAW),**change})
 def test_exact_edges_inside_and_empty_scope_explicit(self):
  out=classify_control_points([row([[0,0],[970,720]])],[0,0,970,720]);self.assertTrue(out['allSupportedControlPointsInBounds']);self.assertEqual(out['controlPointsChecked'],2);self.assertIsNone(out['designPassed']);self.assertEqual(classify_control_points([],[0,0,970,720])['objectsChecked'],0)
 def test_all_four_sides_and_corner_membership(self):
  out=classify_control_points([row([[-1,-1],[971,721],[0,720]])],[0,0,970,720]);self.assertEqual([f['sides'] for f in out['findings']],[['left','top'],['right','bottom']]);self.assertEqual([f['controlPointIndex'] for f in out['findings']],[0,1])
 def test_margin_is_explicit_and_strict(self):
  out=classify_control_points([row([[0,0],[10,10],[960,710],[970,720]])],[0,0,970,720],10);self.assertEqual([f['controlPointIndex'] for f in out['findings']],[0,3])
  for margin in (True,-1,360,1000001):
   with self.assertRaises(CadenceError):classify_control_points([],[0,0,970,720],margin)
 def test_unsupported_and_finding_budget_are_failures_not_partial_success(self):
  with self.assertRaises(CadenceError):classify_control_points([row([],kind='unsupported')],[0,0,970,720])
  with self.assertRaises(CadenceError):classify_control_points([row([[-1,0]]*1001)],[0,0,970,720])
 def test_object_and_point_budgets(self):
  with self.assertRaises(CadenceError):classify_control_points([row([])]*4097,[0,0,970,720])
  with self.assertRaises(CadenceError):classify_control_points([row([[0,0]]*65537)],[0,0,970,720])
