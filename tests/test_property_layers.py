import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_property_layers import read_property_layers
from cadence_mcp.core import CadenceError, Config
from cadence_mcp.server import create_server
from test_part_geometry import PART, inspection


def document():
    return {"partId": PART, "schematicName": "main", "pageName": "page", "reference": "U1",
            "effective": [{"name": "Value", "value": "1k"}, {"name": "Part Reference", "value": "U1A"}],
            "user": [{"name": "PCB Footprint", "value": ""}],
            "display": [{"name": "Part Reference", "value": "U1A", "location": [-37, 13],
                         "rotationCode": 0, "displayTypeCode": 1, "colorCode": 48}]}


def worker(config, script, args, cwd):
    assert script == "inspect_property_layers.tcl"
    Path(args[1]).write_text(json.dumps(document()), encoding="utf-8")


class LayersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        install = root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        inputs = root / "inputs"
        inputs.mkdir()
        self.source = inputs / "fixture.dsn"
        self.source.write_bytes(b"mock design")
        self.config = Config(install, root / "work", (inputs,))
        self.capture = CaptureService(self.config)
        ws = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", inspection):
            self.session = self.capture.open(ws["workspaceId"])
        self.sid = self.session["sessionId"]

    def test_layers_preserve_empty_value_and_unit_display_reference(self):
        with patch("cadence_mcp.capture_property_layers.run_tcl", worker):
            row = read_property_layers(self.capture, self.sid, PART)
        self.assertEqual(row["reference"], "U1")
        self.assertEqual(row["display"][0]["value"], "U1A")
        self.assertEqual(row["user"][0]["value"], "")
        self.assertEqual(row["displayCoordinateSpace"], "owner_local")
        self.assertNotIn("origin", row["effective"][0])
        directory = self.capture.workspaces[self.session["workspaceId"]]["directory"]
        self.assertFalse(list(directory.glob("property-layers-*.json")))

    def test_wrong_identity_and_bad_layer_rows_rejected(self):
        bad = [{}, [], {**document(), "reference": "U10"}]
        for key, value in (("user", {}), ("effective", [{"name": "V", "value": 1}]),
                           ("user", [{"name": "V", "value": ""}] * 2),
                           ("user", [{"name": "", "value": ""}])):
            bad.append({**document(), key: value})
        for key, value in (("rotationCode", True), ("location", [1.5, 1]), ("displayTypeCode", "1"), ("colorCode", None)):
            row = document()
            row["display"][0][key] = value
            bad.append(row)
        for row in bad:
            def invalid(config, script, args, cwd): Path(args[1]).write_text(json.dumps(row), encoding="utf-8")
            with patch("cadence_mcp.capture_property_layers.run_tcl", invalid), self.assertRaises(CadenceError):
                read_property_layers(self.capture, self.sid, PART)

    def test_unknown_id_and_stale_session(self):
        with patch("cadence_mcp.capture_property_layers.run_tcl") as native:
            with self.assertRaises(CadenceError): read_property_layers(self.capture, self.sid, "foreign")
            self.capture.sessions[self.sid]["design"].write_bytes(b"changed")
            with self.assertRaises(CadenceError) as error: read_property_layers(self.capture, self.sid, PART)
            self.assertEqual(error.exception.code, "target_changed")
            native.assert_not_called()

    def test_mcp_strict_layers_read(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                ws = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", inspection):
                    opened = await client.call_tool("capture_open", {"workspaceId": ws.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"], "partId": PART}
                with patch("cadence_mcp.capture_property_layers.run_tcl", worker):
                    checked = await client.call_tool("capture_get_property_layers", args)
                self.assertFalse(checked.is_error)
                self.assertEqual(checked.structured_content["data"]["counts"]["display"], 1)
                self.assertTrue((await client.call_tool("capture_get_property_layers", {**args, "eval": "no"})).is_error)
        asyncio.run(exercise())
