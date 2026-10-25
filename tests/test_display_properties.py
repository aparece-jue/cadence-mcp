import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_display_properties import CaptureDisplayProperties
from cadence_mcp.core import CadenceError, Config
from cadence_mcp.server import create_server
from test_connections import design


def worker(config, script, args, cwd):
    Path(args[1]).write_text(json.dumps(design()), encoding="utf-8")


def layers():
    return {"schematicName": "main", "pageName": "page1", "reference": "U1",
            "effective": [{"name": "Value", "value": "1k"}], "user": [],
            "display": [{"name": "Value", "value": "1k", "location": [-10, 15], "rotationCode": 0, "displayTypeCode": 1, "colorCode": 48},
                        {"name": "Part Reference", "value": "U1", "location": [0, -10], "rotationCode": 0, "displayTypeCode": 1, "colorCode": 48}]}


class DisplayPropertyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install = self.root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        inputs = self.root / "inputs"
        inputs.mkdir()
        self.source = inputs / "fixture.dsn"
        self.source.write_bytes(b"mock design")
        self.config = Config(install, self.root / "work", (inputs,))
        self.capture = CaptureService(self.config)
        ws = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", worker):
            self.session = self.capture.open(ws["workspaceId"])
        self.sid = self.session["sessionId"]
        self.editor = CaptureDisplayProperties(self.config, self.capture)

    def plan(self, location=None, rotation=None, mode=2):
        with patch("cadence_mcp.capture_display_properties.read_property_layers", return_value=layers()):
            return self.editor.plan(self.sid, "u", "Value", location, rotation, mode)

    def test_partial_change_keeps_unrequested_layout_data_and_color(self):
        plan = self.plan(location=[-55, 42], rotation=1)
        expected = plan["preview"]["expectedDisplay"]
        self.assertEqual(expected, {**layers()["display"][0], "location": [-55, 42], "rotationCode": 1, "displayTypeCode": 2})
        self.assertFalse(plan["sourceWillBeModified"])

    def test_invalid_codes_points_noop_missing_or_shared_target_rejected(self):
        for args in (([True, 1], None, 1), ([1, 2.5], None, 1), ([1], None, 1), (None, 4, 1),
                     (None, None, 5), (None, None, None)):
            with self.assertRaises(CadenceError): self.plan(*args)
        with patch("cadence_mcp.capture_display_properties.read_property_layers", return_value=layers()):
            with self.assertRaises(CadenceError): self.editor.plan(self.sid, "u", "Reference", None, None, 0)
        self.capture.sessions[self.sid]["data"]["part"].append({**design()["part"][0], "objectId": "shared"})
        with self.assertRaises(CadenceError): self.plan()

    def test_independent_readback_checks_layout_and_all_data_properties(self):
        plan = self.plan(location=[-55, 42], rotation=1)
        directory, _, row = self.editor._load(plan["planId"])
        (directory / "design.dsn").write_bytes(b"mock output")
        after = layers()
        after["display"][0] = row["plan"]["payload"]["expectedDisplay"]
        with patch("cadence_mcp.capture.run_tcl", worker), patch("cadence_mcp.capture_display_properties.read_property_layers", return_value=after):
            result = self.editor.verify(directory, row["plan"]["payload"], False)
        self.assertTrue(result["dataPropertiesPreserved"])
        self.assertIsNone(result["designPassed"])
        for change in ("target", "data", "other_display"):
            bad = deepcopy(after)
            if change == "target": bad["display"][0]["rotationCode"] = 3
            if change == "data": bad["effective"][0]["value"] = "changed"
            if change == "other_display": bad["display"][1]["location"] = [9, 9]
            with patch("cadence_mcp.capture.run_tcl", worker), patch("cadence_mcp.capture_display_properties.read_property_layers", return_value=bad):
                with self.assertRaises(CadenceError): self.editor.verify(directory, row["plan"]["payload"], False)

    def test_mcp_types_protected_font_and_pending_cancel(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                ws = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": ws.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"], "partId": "u", "propertyName": "Value", "displayTypeCode": 0}
                with patch("cadence_mcp.capture_display_properties.read_property_layers", return_value=layers()):
                    planned = await client.call_tool("capture_plan_display_property", args)
                self.assertFalse(planned.is_error)
                plan = planned.structured_content["data"]
                cancelled = await client.call_tool("capture_cancel_display_property", {"planId": plan["planId"], "planDigest": plan["planDigest"]})
                self.assertFalse(cancelled.is_error)
                for extra in ({"font": "Arial"}, {"location": [True, 1]}, {"rotationCode": 90}):
                    self.assertTrue((await client.call_tool("capture_plan_display_property", {**args, **extra})).is_error)
        asyncio.run(exercise())
