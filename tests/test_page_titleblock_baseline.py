from copy import deepcopy
import unittest

from cadence_mcp.capture_page_edit import graphic_digest, titleblock_content
from cadence_mcp.core import CadenceError


class PageTitleblockBaselineTests(unittest.TestCase):
    def test_generated_context_is_validated_and_user_override_is_preserved(self):
        attrs = {
            "properties": [
                {"name": "Design File Name", "value": r"C:\CASE\SOURCE.DSN"},
                {"name": "Page Name", "value": "Original"},
                {"name": "Page Modify Time", "value": "17:32:51"},
                {"name": "Title", "value": "Project title"},
            ],
            "userProperties": [{"name": "Page Modify Time", "value": "17:32:51", "nativeType": 0}],
        }
        before = titleblock_content(attrs, "Original", "Renamed", r"C:\case\source.dsn")
        self.assertEqual({row["name"]: row["value"] for row in before["properties"]},
                         {"Design File Name": None, "Page Name": "Renamed", "Page Modify Time": "17:32:51", "Title": "Project title"})
        self.assertEqual(before["userProperties"], attrs["userProperties"])
        for field in ("Design File Name", "Page Name"):
            invalid = deepcopy(attrs)
            next(prop for prop in invalid["properties"] if prop["name"] == field)["value"] = "wrong"
            with self.subTest(field=field), self.assertRaises(CadenceError):
                titleblock_content(invalid, "Original", "Renamed", r"C:\case\source.dsn")

    def test_digest_binds_titleblock_identity_fields_and_user_data(self):
        base = {"schematic": [{"objectId": "s", "name": "S"}],
                "page": [{"objectId": "p", "schematicId": "s", "name": "Original"}], "part": []}
        expected = deepcopy(base)
        expected["page"][0]["name"] = "Renamed"
        props = [
            {"name": "Design File Name", "value": r"C:\case\source.dsn"},
            {"name": "Page Name", "value": "Original"},
            {"name": "Design Modify Date", "value": "Day before"},
            {"name": "Page Modify Time", "value": "17:32:51"},
            {"name": "Title", "value": "Keep me"},
        ]
        source = [{"kind": "titleblock", "pageId": "p", "nativeId": 1,
                   "attributes": {"location": [10, 20], "properties": props,
                                  "userProperties": [{"name": "Page Modify Time", "value": "17:32:51", "nativeType": 0}]}}]
        before = graphic_digest(expected, source, titleblock_design=r"C:\case\source.dsn", original=base)
        saved = deepcopy(source)
        saved_props = saved[0]["attributes"]["properties"]
        saved_props[0]["value"] = r"C:\CASE\OUTPUT.DSN"
        saved_props[1]["value"] = "Renamed"
        saved_props[2]["value"] = "Day after"

        def digest(rows):
            return graphic_digest(expected, rows, titleblock_design=r"C:\case\output.dsn")

        self.assertEqual(before, digest(saved))
        for variant in ("removed_generated_field", "changed_title", "changed_user_field", "changed_user_type", "changed_identity"):
            altered = deepcopy(saved)
            row = altered[0]
            if variant == "removed_generated_field":
                row["attributes"]["properties"].pop(2)
            elif variant == "changed_title":
                row["attributes"]["properties"][-1]["value"] = "Lost"
            elif variant == "changed_user_field":
                row["attributes"]["userProperties"][0]["value"] = "Different"
                row["attributes"]["properties"][3]["value"] = "Different"
            elif variant == "changed_user_type":
                row["attributes"]["userProperties"][0]["nativeType"] = 1
            else:
                row["nativeId"] = 2
            with self.subTest(variant=variant):
                self.assertNotEqual(before, digest(altered))
