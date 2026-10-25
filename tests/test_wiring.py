import unittest
from cadence_mcp.wiring import analyze_wiring
from cadence_mcp.core import CadenceError

def data(*polylines):
    return {"schematic":[],"page":[{"objectId":"p"}],"wire":[
        {"objectId":f"w{i}","pageId":"p","net":"SAME_LABEL", "points":points}
        for i,points in enumerate(polylines)]}

class WiringTests(unittest.TestCase):
    def test_proper_crossing_is_candidate_not_connection(self):
        result=analyze_wiring(data([[0,5],[10,5]],[[5,0],[5,10]]))
        self.assertEqual(result["countsByRule"],{"WIRE-CROSSING-CANDIDATE":1})
        self.assertEqual(result["findings"][0]["point"],[5,5])
        self.assertEqual(result["findings"][0]["electricalConnection"],"not_evaluated")
        self.assertIsNone(result["designPassed"])

    def test_shared_endpoint_and_bend_not_penalized(self):
        self.assertEqual(analyze_wiring(data([[0,0],[10,0],[10,10]]))["findings"],[])
        self.assertEqual(analyze_wiring(data([[0,0],[10,0]],[[10,0],[10,10]]))["findings"],[])

    def test_t_contact_separate_from_crossing(self):
        r=analyze_wiring(data([[0,5],[10,5]],[[5,5],[5,10]]))
        self.assertEqual(r["countsByRule"],{"WIRE-T-CONTACT-CANDIDATE":1})

    def test_reverse_overlap_and_collinear_touch(self):
        r=analyze_wiring(data([[10,0],[0,0]],[[5,0],[15,0]]))
        self.assertEqual(r["findings"][0]["start"],[5,0])
        self.assertEqual(r["findings"][0]["end"],[10,0])
        self.assertEqual(analyze_wiring(data([[0,0],[5,0]],[[5,0],[10,0]]))["findings"],[])

    def test_pages_are_isolated(self):
        doc=data([[0,5],[10,5]],[[5,0],[5,10]])
        doc["page"].append({"objectId":"other"})
        doc["wire"][1]["pageId"]="other"
        self.assertEqual(analyze_wiring(doc)["findings"],[])

    def test_diagonal_intersections_are_included_in_linear_coverage(self):
        r=analyze_wiring(data([[0,0],[10,10]]))
        self.assertTrue(r["geometryComplete"])
        self.assertEqual(r["countsByRule"],{"WIRE-NON-ORTHOGONAL":1})

    def test_zero_length_and_malformed_coordinates(self):
        self.assertEqual(analyze_wiring(data([[1,1],[1,1]]))["countsByRule"],{"WIRE-ZERO-LENGTH":1})
        for bad in [[[True,1],[2,1]],[[1.5,1],[2,1]]]:
            with self.assertRaises(CadenceError): analyze_wiring(data(bad))

    def test_unknown_page_and_resource_limit(self):
        doc=data([[0,0],[1,0]])
        doc["wire"][0]["pageId"]="unknown"
        with self.assertRaises(CadenceError): analyze_wiring(doc)
        with self.assertRaises(CadenceError): analyze_wiring(data(*([[[0,0],[1,0]]]*2001)))
