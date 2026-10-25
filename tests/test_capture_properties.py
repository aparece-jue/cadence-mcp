import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_properties import read_part_properties
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.server import create_server


def inspection(config, script, args, cwd):
    Path(args[1]).write_text(json.dumps({
        "schematic": [{"objectId": "schematic-1", "name": "原理图"}],
        "page": [{"objectId": "schematic-1/page-1", "schematicId": "schematic-1", "name": "page"}],
        "part": [{"objectId": f"schematic-1/page-1/part-{index}", "pageId": "schematic-1/page-1",
                  "schematicId": "schematic-1", "reference": "U1"} for index in (1, 2)], "pin": []
    }), encoding="utf-8")


def property_document(part_id):
    return {"partId": part_id, "schematicName": "原理图", "pageName": "page", "reference": "U1",
            "properties": [{"name": "Value", "value": "中文|{}[]$;\"\\\n"},
                           {"name": "PCB Footprint", "value": ""}]}


class PropertyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        install = root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        inputs = root / "input"
        inputs.mkdir()
        self.source = inputs / "fixture.dsn"
        self.source.write_bytes(b"mock input")
        self.config = Config(install, root / "work", (inputs,))
        self.capture = CaptureService(self.config)
        self.ws = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", inspection):
            self.session = self.capture.open(self.ws["workspaceId"])
        self.sid = self.session["sessionId"]
        self.directory = self.capture.workspaces[self.ws["workspaceId"]]["directory"]

    @staticmethod
    def worker(config, script, args, cwd):
        assert script == "inspect_part_properties.tcl"
        Path(args[1]).write_text(json.dumps(property_document(args[2])), encoding="utf-8")

    def test_duplicate_references_are_selected_by_part_id_and_transient_file_removed(self):
        before = sha256(self.source)
        for index in (1, 2):
            part_id = f"schematic-1/page-1/part-{index}"
            with patch("cadence_mcp.capture_properties.run_tcl", self.worker):
                result = read_part_properties(self.capture, self.sid, part_id)
            self.assertEqual(result["partId"], part_id)
            self.assertEqual(result["revision"], self.session["revision"])
            self.assertEqual(result["items"][1]["value"], "中文|{}[]$;\"\\\n")
            self.assertEqual(result["items"][0]["value"], "")
            self.assertNotIn("editable", result["items"][0])
        self.assertEqual(sha256(self.source), before)
        self.assertEqual(list(self.directory.glob("part-properties-*.json")), [])

    def test_unknown_part_and_stale_session_do_not_launch_worker(self):
        with patch("cadence_mcp.capture_properties.run_tcl") as worker:
            with self.assertRaises(CadenceError): read_part_properties(self.capture, self.sid, "foreign-part")
            (self.directory / "design.dsn").write_bytes(b"changed")
            with self.assertRaises(CadenceError) as error:
                read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
            self.assertEqual(error.exception.code, "target_changed")
            worker.assert_not_called()

    def test_changed_during_worker_is_rejected(self):
        def mutate(config, script, args, cwd):
            self.worker(config, script, args, cwd)
            Path(args[0]).write_bytes(b"changed")
        with patch("cadence_mcp.capture_properties.run_tcl", mutate), self.assertRaises(CadenceError) as error:
            read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
        self.assertEqual(error.exception.code, "target_changed")

    def test_inconsistent_parent_is_rejected_before_worker(self):
        self.capture.sessions[self.sid]["data"]["page"][0]["schematicId"] = "foreign"
        with patch("cadence_mcp.capture_properties.run_tcl") as worker:
            with self.assertRaises(CadenceError) as error:
                read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
            self.assertEqual(error.exception.code, "invalid_worker_result")
            worker.assert_not_called()

    def test_malformed_or_wrong_identity_never_returns_properties(self):
        bad_rows = []
        for field in ("partId", "schematicName", "pageName", "reference"):
            row = property_document("schematic-1/page-1/part-1")
            row[field] = "other"
            bad_rows.append(row)
        for props in ({}, [1], [{"name": "", "value": ""}], [{"name": "v", "value": 1}],
                      [{"name": "v", "value": "x", "editable": True}],
                      [{"name": "v", "value": ""}] * 2, [{"name": str(i), "value": ""} for i in range(513)]):
            bad_rows.append({**property_document("schematic-1/page-1/part-1"), "properties": props})
        bad_rows += [{}, [], {**property_document("schematic-1/page-1/part-1"), "extra": "x"}]
        for row in bad_rows:
            def invalid(config, script, args, cwd):
                Path(args[1]).write_text(json.dumps(row), encoding="utf-8")
            with patch("cadence_mcp.capture_properties.run_tcl", invalid), self.assertRaises(CadenceError) as error:
                read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
            self.assertEqual(error.exception.code, "invalid_worker_result")

    def test_missing_large_result_and_worker_failure(self):
        def oversized(config, script, args, cwd):
            Path(args[1]).write_bytes(b"x" * (1024 * 1024 + 1))
        for worker in (lambda *args: None, oversized):
            with patch("cadence_mcp.capture_properties.run_tcl", worker), self.assertRaises(CadenceError):
                read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
        with patch("cadence_mcp.capture_properties.run_tcl", side_effect=CadenceError("worker_crashed", "fixture")):
            with self.assertRaises(CadenceError) as error:
                read_part_properties(self.capture, self.sid, "schematic-1/page-1/part-1")
        self.assertEqual(error.exception.code, "worker_crashed")

    def test_mcp_property_read_and_strict_inputs(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                created = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", inspection):
                    opened = await client.call_tool("capture_open", {"workspaceId": created.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"],
                        "partId": "schematic-1/page-1/part-2"}
                with patch("cadence_mcp.capture_properties.run_tcl", self.worker):
                    result = await client.call_tool("capture_get_part_properties", args)
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["data"]["count"], 2)
                extra = await client.call_tool("capture_get_part_properties", {**args, "eval": "forbidden"})
                self.assertTrue(extra.is_error)
                missing = await client.call_tool("capture_get_part_properties", {**args, "partId": "missing"})
                self.assertTrue(missing.is_error)
        asyncio.run(exercise())
