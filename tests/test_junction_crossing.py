import unittest

from cadence_mcp.capture_junction import junction_crossing, junction_groups
from cadence_mcp.capture_wire import geometry_union
from cadence_mcp.core import CadenceError


def wire(wire_id, start, end, page="main"):
    return {"objectId": wire_id, "kind": "wire", "pageId": page, "attributes": {"points": [start, end]}}


class JunctionCrossingTests(unittest.TestCase):
    def setUp(self):
        self.h = wire("h", [100, 350], [300, 350])
        self.v = wire("v", [200, 300], [200, 400])
        self.point = [200, 350]

    def test_proper_crossing_splits_both_paths_and_preserves_page_geometry(self):
        away = wire("away", [100, 100], [300, 100])
        other_page = wire("other-page", [150, 350], [250, 350], page="child")
        result = junction_crossing([self.h, self.v, away, other_page], "main", ["h", "v"], self.point)
        self.assertEqual(result, [
            [[100, 100], [300, 100]], [[100, 350], [200, 350]], [[200, 350], [300, 350]],
            [[200, 300], [200, 350]], [[200, 350], [200, 400]],
        ])
        self.assertEqual(geometry_union(result), geometry_union([w["attributes"]["points"] for w in [self.h, self.v, away]]))

    def test_rejects_t_corner_diagonal_or_overlapping_pair(self):
        alternatives = [
            wire("v", [200, 350], [200, 400]),
            wire("v", [200, 350], [260, 350]),
            wire("v", [150, 300], [250, 400]),
            wire("v", [150, 350], [260, 350]),
        ]
        for other in alternatives:
            with self.subTest(wire=other), self.assertRaises(CadenceError) as error:
                junction_crossing([self.h, other], "main", ["h", "v"], self.point)
            self.assertEqual(error.exception.code, "invalid_junction_crossing")

    def test_rejects_ambiguous_third_arm_and_foreign_id(self):
        arm = wire("extra", [200, 350], [250, 350])
        with self.assertRaises(CadenceError) as error:
            junction_crossing([self.h, self.v, arm], "main", ["h", "v"], self.point)
        self.assertEqual(error.exception.code, "ambiguous_junction_crossing")
        with self.assertRaises(CadenceError) as error:
            junction_crossing([self.h, self.v], "main", ["h", "extra"], self.point)
        self.assertEqual(error.exception.code, "object_not_found")

    def test_group_merge_moves_every_member_of_the_two_nodes_only(self):
        sibling = wire("sibling", [300, 350], [350, 350])
        other = wire("other", [100, 100], [300, 100])
        original = [self.h, self.v, sibling, other]
        saved = junction_crossing(original, "main", ["h", "v"], self.point)
        before = [{"kind": "wire", "schematicName": "S", "pageName": "P",
                   "points": row["attributes"]["points"], "group": group}
                  for row, group in zip(original, ("h", "v", "h", "other"))]
        before.extend([
            {"kind": "pin", "schematicName": "S", "pageName": "P", "reference": "R1", "number": "1", "group": "v"},
            {"kind": "pin", "schematicName": "S", "pageName": "P", "reference": "R1", "number": "2", "group": None},
        ])
        selected = [row["attributes"]["points"] for row in original[:2]]
        pins = [{"reference": "R1", "pinNumber": str(i), "connected": i == 1} for i in (1, 2)]
        groups = junction_groups(before, ("S", "P"), selected, self.point, saved, pins)
        self.assertEqual(groups, [
            {"wireIndexes": [0, 2, 3, 4, 5], "pinIndexes": [0]},
            {"wireIndexes": [1], "pinIndexes": []},
        ])
        before[1]["group"] = "h"
        with self.assertRaises(CadenceError) as error:
            junction_groups(before, ("S", "P"), selected, self.point, saved, pins)
        self.assertEqual(error.exception.code, "junction_already_connected")
