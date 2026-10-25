import asyncio
from copy import deepcopy
import unittest

from mcp import Client
from cadence_mcp.capture_hierarchy import validate_hierarchy
from cadence_mcp.core import CadenceError


def tree():
    return [
        {"occurrenceId": "root", "parentId": None, "depth": 0, "path": "/", "hierarchicalPath": "/", "reference": "", "properties": []},
        {"occurrenceId": "a", "parentId": "root", "depth": 1, "path": "/B1", "hierarchicalPath": "/B1", "reference": "B1", "properties": []},
        {"occurrenceId": "b", "parentId": "root", "depth": 1, "path": "/B2", "hierarchicalPath": "/B2", "reference": "B2", "properties": []},
    ]


class InternalHierarchyTests(unittest.TestCase):
    def test_valid_tree_is_not_mutated(self):
        rows = tree()
        before = deepcopy(rows)
        validate_hierarchy(rows)
        self.assertEqual(rows, before)

    def test_cycle_parent_depth_duplicates_and_bad_property_rejected(self):
        bad = [[], {}, [tree()[1]]]
        for index, key, value in ((1, "parentId", "b"), (1, "depth", 3), (1, "depth", True),
                                  (2, "reference", "B1"), (2, "occurrenceId", "a"),
                                  (1, "properties", [{"name": "V", "value": 1}])):
            rows = tree()
            rows[index][key] = value
            bad.append(rows)
        for rows in bad:
            with self.assertRaises(CadenceError): validate_hierarchy(rows)

    def test_multiunit_raw_paths_may_repeat(self):
        rows = tree()
        rows[1].update(path="/U3", reference="U3A")
        rows[2].update(path="/U3", reference="U3B")
        validate_hierarchy(rows)

    def test_same_unit_reference_in_distinct_contexts(self):
        rows = tree()
        for parent in ("a", "b"):
            rows.append({"occurrenceId": parent+"-unit", "parentId": parent,
                         "depth": 2, "path": "/U3", "hierarchicalPath": "",
                         "reference": "U3A", "properties": []})
        validate_hierarchy(rows)

    def test_depth_and_property_limits_rejected(self):
        rows = tree()
        rows[1]["depth"] = 65
        with self.assertRaises(CadenceError): validate_hierarchy(rows)
        rows = tree()
        rows[1]["properties"] = [{"name": str(i), "value": "x"} for i in range(513)]
        with self.assertRaises(CadenceError): validate_hierarchy(rows)
