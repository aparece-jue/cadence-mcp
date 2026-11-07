import unittest

from cadence_mcp.core import CadenceError
from cadence_mcp.schematic_dependencies import classify_dependencies, require_unreferenced


def unit(reference, view="", view_type=0, library="", primitive=1, external=False, owner="ROOT"):
    return {"partId": reference, "nativeId": 1, "schematicName": owner, "pageName": "P",
            "reference": reference, "isExternalDesignPart": external,
            "contents": {"viewName": view, "viewType": view_type, "libraryName": library, "primitive": primitive}}


class SchematicDependencyTests(unittest.TestCase):
    def test_scan_preserves_repeated_and_unreachable_definition_references(self):
        graph = classify_dependencies(["ROOT", "Child", "Unused", "Orphan"], [
            unit("X1", "Child", 1, primitive=0), unit("X2", "CHILD", 1, primitive=0),
            unit("X3", "Child", 1, primitive=0, owner="Orphan"), unit("R1"),
        ])
        self.assertEqual([row["reference"] for row in graph["incoming"]["Child"]], ["X1", "X2", "X3"])
        require_unreferenced(graph, "Unused")
        with self.assertRaises(CadenceError) as caught:
            require_unreferenced(graph, "Child")
        self.assertEqual(caught.exception.code, "schematic_referenced")

    def test_uncertain_bindings_cannot_prove_empty_incoming_references(self):
        for part in (unit("X1", "Missing", 1), unit("X1", "Child", 1, library="other.dsn"),
                     unit("X1", "Child", 1, external=True), unit("X1", view_type=42),
                     unit("X1", primitive=0)):
            with self.subTest(part=part), self.assertRaises(CadenceError) as caught:
                require_unreferenced(classify_dependencies(["ROOT", "Child"], [part]), "Child")
            self.assertEqual(caught.exception.code, "schematic_dependencies_unverified")

    def test_case_ambiguous_schematic_names_refused(self):
        with self.assertRaises(CadenceError) as caught:
            classify_dependencies(["Child", "CHILD"], [])
        self.assertEqual(caught.exception.code, "ambiguous_target")
