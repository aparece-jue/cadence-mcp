import unittest

from cadence_mcp.capture_design_save_as import design_file_name
from cadence_mcp.capture_page_edit import titleblock_content
from cadence_mcp.core import CadenceError


class SaveAsFileNameTests(unittest.TestCase):
    def test_preserves_requested_leaf(self):
        for value in ("design.dsn", "Release Candidate 2.DSN", "main.rev-2.dsn", "_copy.dsn"):
            self.assertEqual(design_file_name(value), value)

    def test_rejects_windows_paths_devices_and_unsafe_suffixes(self):
        for value in ("../file.dsn", r"sub\file.dsn", r"C:\file.dsn", "C:file.dsn",
                      "NUL.dsn", "AUX.extra.dsn", "LPT1.dsn", "con .bak.dsn",
                      "foo.dsn:alternate", "foo..dsn", "foo .dsn", "LPT\u00b9.dsn", "file.d\u017fn", "file.dsn "):
            with self.subTest(value=value), self.assertRaises(CadenceError) as caught:
                design_file_name(value)
            self.assertEqual(caught.exception.code, "invalid_design_file_name")

    def test_generated_titleblock_name_follows_file_but_user_name_is_preserved(self):
        prop = {"name": "Design Name", "value": "RELEASE CANDIDATE 2"}
        attrs = {"properties": [prop], "userProperties": []}
        design = r"C:\case\Release Candidate 2.DSN"
        self.assertIsNone(titleblock_content(attrs, "P", "P", design, named_context=True)["properties"][0]["value"])
        self.assertEqual(titleblock_content(attrs, "P", "P", design)["properties"][0], prop)
        with self.assertRaises(CadenceError):
            titleblock_content(attrs, "P", "P", r"C:\case\different.dsn", named_context=True)
        attrs["userProperties"] = [{**prop, "nativeType": 0}]
        self.assertEqual(titleblock_content(attrs, "P", "P", r"C:\case\different.dsn", named_context=True)["properties"][0], prop)
