import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_geometry import read_part_geometry
from cadence_mcp.core import CadenceError, Config
from cadence_mcp.server import create_server


PART = "schematic-1/page-1/part-1"


def inspection(config, script, args, cwd):
    Path(args[1]).write_text(json.dumps({"schematic": [{"objectId": "s", "name": "main"}],
        "page": [{"objectId": "p", "schematicId": "s", "name": "page"}],
        "part": [{"objectId": PART, "schematicId": "s", "pageId": "p", "reference": "U1"}],
        "pin": [{"objectId": PART + "/pin-1", "partId": PART, "schematicId": "s", "pageId": "p",
                 "reference": "U1", "number": "1", "name": "I", "connected": True, "net": "IN"}]}), encoding="utf-8")


def geometry():
    return {"partId": PART, "schematicName": "main", "pageName": "page", "reference": "U1",
            "location": [330, 220], "rotationCode": 3, "mirrorCode": 1,
            "pins": [{"pinId": PART + "/pin-1", "number": "1", "name": "I", "hotSpot": [350, 190]}]}


def worker(config, script, args, cwd):
    assert script == "inspect_part_geometry.tcl"
    Path(args[1]).write_text(json.dumps(geometry()), encoding="utf-8")


class GeometryTests(unittest.TestCase):
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
        self.ws = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", inspection):
            self.session = self.capture.open(self.ws["workspaceId"])
        self.sid = self.session["sessionId"]

    def test_raw_codes_and_transformed_hotspot_no_electrical_claim(self):
        with patch("cadence_mcp.capture_geometry.run_tcl", worker):
            result = read_part_geometry(self.capture, self.sid, PART)
        self.assertEqual(result["rotationCode"], 3)
        self.assertEqual(result["mirrorCode"], 1)
        self.assertEqual(result["pins"][0]["hotSpot"], [350, 190])
        self.assertNotEqual(result["pins"][0]["hotSpot"], result["location"])
        self.assertFalse(result["electricalConnectivityVerified"])
        directory = self.capture.workspaces[self.ws["workspaceId"]]["directory"]
        self.assertFalse(list(directory.glob("part-geometry-*.json")))

    def test_unknown_stale_and_parent_inconsistency_rejected(self):
        with patch("cadence_mcp.capture_geometry.run_tcl") as native:
            with self.assertRaises(CadenceError): read_part_geometry(self.capture, self.sid, "foreign")
            self.capture.sessions[self.sid]["data"]["page"][0]["schematicId"] = "other"
            with self.assertRaises(CadenceError): read_part_geometry(self.capture, self.sid, PART)
            self.capture.sessions[self.sid]["design"].write_bytes(b"changed")
            with self.assertRaises(CadenceError) as error: read_part_geometry(self.capture, self.sid, PART)
            self.assertEqual(error.exception.code, "target_changed")
            native.assert_not_called()

    def test_bad_shapes_or_mismatched_pin_id_number_name_rejected(self):
        bad = [{}, [], {**geometry(), "extra": 1}]
        for key, value in (("rotationCode", True), ("mirrorCode", "1"), ("location", [1, 2.5]),
                           ("partId", "foreign"), ("pageName", "other"), ("pins", [])):
            bad.append({**geometry(), key: value})
        for key, value in (("pinId", "foreign"), ("name", "O"), ("number", "2"), ("hotSpot", [True, 1])):
            row = geometry()
            row["pins"][0][key] = value
            bad.append(row)
        row = geometry()
        row["pins"] *= 2
        bad.append(row)
        for row in bad:
            def invalid(config, script, args, cwd):
                Path(args[1]).write_text(json.dumps(row), encoding="utf-8")
            with patch("cadence_mcp.capture_geometry.run_tcl", invalid), self.assertRaises(CadenceError):
                read_part_geometry(self.capture, self.sid, PART)

    def test_change_during_worker_and_worker_crash(self):
        def mutate(config, script, args, cwd):
            worker(config, script, args, cwd)
            Path(args[0]).write_bytes(b"changed")
        with patch("cadence_mcp.capture_geometry.run_tcl", mutate), self.assertRaises(CadenceError) as error:
            read_part_geometry(self.capture, self.sid, PART)
        self.assertEqual(error.exception.code, "target_changed")

    def test_mcp_read_and_strict_inputs(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                ws = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", inspection):
                    opened = await client.call_tool("capture_open", {"workspaceId": ws.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"], "partId": PART}
                with patch("cadence_mcp.capture_geometry.run_tcl", worker):
                    result = await client.call_tool("capture_get_part_geometry", args)
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["data"]["pins"][0]["hotSpot"], [350, 190])
                self.assertTrue((await client.call_tool("capture_get_part_geometry", {**args, "eval": "no"})).is_error)
        asyncio.run(exercise())
