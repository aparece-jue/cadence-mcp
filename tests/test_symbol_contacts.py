import unittest
from cadence_mcp.capture_symbol_contacts import analyze_symbol_contacts
from cadence_mcp.core import CadenceError
def vector(points,kind='line',oid='v'):
 return {'objectId':oid,'partId':'part','pageId':'page','pageControlPoints':points,'kind':kind}
def wire(points,page='page',oid='w'):
 return {'objectId':oid,'kind':'wire','pageId':page,'attributes':{'points':points}}
class SymbolContacts(unittest.TestCase):
 def test_exact_fractional_crossing_and_no_clearance_pass(self):
  r=analyze_symbol_contacts([vector([[0,0],[3,3]])],[wire([[0,2],[3,0]])],'part','page');f=r['findings'][0]
  self.assertEqual(f['pointExact'],[{'numerator':6,'denominator':5}]*2);self.assertEqual(f['contactKind'],'crossing');self.assertIsNone(r['designPassed']);self.assertFalse(r['renderedClearanceVerified'])
 def test_t_contact_overlap_and_shared_endpoint_policy(self):
  r=analyze_symbol_contacts([vector([[0,0],[10,0]])],[wire([[5,0],[5,10]])],'part','page');self.assertEqual(r['countsByContactKind'],{'t_contact':1})
  r=analyze_symbol_contacts([vector([[10,0],[0,0]])],[wire([[5,0],[15,0]])],'part','page');self.assertEqual(r['findings'][0]['start'],[5,0]);self.assertEqual(r['findings'][0]['end'],[10,0])
  self.assertEqual(analyze_symbol_contacts([vector([[0,0],[10,0]])],[wire([[10,0],[10,10]])],'part','page')['findings'],[])
 def test_cross_page_contacts_excluded(self):
  r=analyze_symbol_contacts([vector([[0,0],[10,0]])],[wire([[5,-5],[5,5]],page='other')],'part','page');self.assertEqual(r['findings'],[]);self.assertEqual(r['wiresOutsidePageSkipped'],1)
 def test_skipped_text_and_empty_scope_remain_explicit(self):
  r=analyze_symbol_contacts([vector([[0,0]],kind='text')],[],'part','page');self.assertFalse(r['linearBoundaryCoverageComplete']);self.assertEqual(len(r['skippedVectors']),1)
  self.assertEqual(analyze_symbol_contacts([],[],'part','page')['findings'],[])
 def test_closed_box_and_polygon_boundaries(self):
  for kind in ('box','polygon'):
   r=analyze_symbol_contacts([vector([[0,0],[10,0],[10,10],[0,10]],kind)],[wire([[-5,5],[15,5]])],'part','page');self.assertEqual(len(r['findings']),2)
 def test_invalid_identity_coordinates_and_duplicate_objects_refused(self):
  for vs,ws in (([vector([[False,0],[1,1]])],[]),([vector([[0,0],[1,1]])]*2,[]),([dict(vector([[0,0],[1,1]]),partId='foreign')],[]),([],[wire([[0,0],[2**32,0]])])):
   with self.assertRaises(CadenceError):analyze_symbol_contacts(vs,ws,'part','page')
 def test_degenerate_segments_do_not_create_contacts(self):
  r=analyze_symbol_contacts([vector([[0,0],[0,0]])],[wire([[0,0],[0,0]])],'part','page');self.assertEqual(r['findings'],[])
 def test_pair_budget_refuses_before_analysis(self):
  vs=[vector([[0,i],[10,i]],oid='v'+str(i)) for i in range(1001)];ws=[wire([[i,0],[i,10]],oid='w'+str(i)) for i in range(1000)]
  with self.assertRaises(CadenceError) as e:analyze_symbol_contacts(vs,ws,'part','page')
  self.assertEqual(e.exception.code,'geometry_limit')
