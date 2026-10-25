import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_objects import query_objects, validate_inventory
from cadence_mcp.core import CadenceError, Config
from cadence_mcp.server import create_server
from test_connections import design


def inventory(mode):
    baseline = design()
    data = {"schematic": baseline["schematic"], "page": baseline["page"], "objects": []}
    def add(kind, oid, attrs):
        data["objects"].append({"kind": kind, "objectId": oid, "pageId": "p", "nativeId": 1, "objectType": 10, "attributes": attrs})
    if mode == "connections":
        add("wire", "w1", {"net": "IN", "points": [[0, 0], [10, 0]]})
        add("wire", "w2", {"net": "OUT", "points": [[0, 10], [10, 10]]})
        add("alias", "a", {"wireId": "w1", "name": "中文|[]$", "location": [5, 0]})
        add("nc", "nc", {"partId": "u", "pinId": "pin2", "reference": "U1", "number": "2", "hotSpot": [10, 10]})
        for kind in ("global", "port", "offpage"):
            add(kind, kind, {"name": "N", "sourceSymbol": "CAPSYM", "location": [20, 20], "hotSpot": [20, 30],
                            "rotationCode": 1, "mirrorCode": 0, "isBus": False})
    else:
        base = {"name": "图形", "location": [0, 0], "rotationCode": 0, "mirrorCode": 0, "bounds": [0, 0, 20, 10]}
        add("part_bounds", "pb", {**base, "partId": "u", "reference": "U1"})
        add("display_property", "dp", {"partId": "u", "name": "Value", "value": "1k", "location": [-4, 7],
            "rotationCode": 0, "displayTypeCode": 1, "colorCode": 48, "bounds": [0, 0, 0, 0], "boundsDirty": True})
        add("graphic", "g", {**base, "text": "说明\n第二行"})
        add("titleblock", "t", {**base, "text": None, "properties": [{"name": "Title", "value": ""}]})
    return data


def worker(config, script, args, cwd):
    assert script == "inspect_page_objects.tcl"
    Path(args[1]).write_text(json.dumps(inventory(args[2]), ensure_ascii=False), encoding="utf-8")


class InventoryValidationTests(unittest.TestCase):
    def test_all_kinds_and_empty_values_are_valid_without_mutation(self):
        for mode in ("connections", "graphics"):
            data = inventory(mode)
            before = deepcopy(data)
            validate_inventory(data, design(), mode)
            self.assertEqual(data, before)

    def test_missing_alias_wire_nc_pin_wrong_parent_and_bool_coordinate_rejected(self):
        variants = []
        for index, field, value in ((2, "wireId", "missing"), (3, "pinId", "missing"),
                                    (3, "number", "99"), (4, "location", [True, 1]), (4, "isBus", 0)):
            data = inventory("connections")
            data["objects"][index]["attributes"][field] = value
            variants.append(data)
        for key, val in (("pageId", "foreign"), ("nativeId", True), ("objectId", "w2"), ("kind", "shell")):
            data = inventory("connections")
            data["objects"][0][key] = val
            variants.append(data)
        variants += [{}, [], {**inventory("connections"), "extra": 1}]
        for data in variants:
            with self.assertRaises(CadenceError): validate_inventory(data, design(), "connections")

    def test_graphic_shape_properties_and_snapshot_parents_rejected(self):
        variants = []
        for index, key, value in ((0, "bounds", [1, 2]), (1, "boundsDirty", 1), (2, "text", 1),
                                  (3, "properties", [{"name": "A", "value": ""}] * 2)):
            data = inventory("graphics")
            data["objects"][index]["attributes"][key] = value
            variants.append(data)
        data = inventory("graphics")
        data["page"][0]["name"] = "wrong page"
        variants.append(data)
        for data in variants:
            with self.assertRaises(CadenceError): validate_inventory(data, design(), "graphics")


class ObjectQueryTests(unittest.TestCase):
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
        self.source.write_bytes(b"mock native input")
        self.config = Config(install, root / "work", (inputs,))
        self.capture = CaptureService(self.config)
        ws = self.capture.create_workspace(str(self.source))
        def base_worker(config, script, args, cwd): Path(args[1]).write_text(json.dumps(design()), encoding="utf-8")
        with patch("cadence_mcp.capture.run_tcl", base_worker):
            self.session = self.capture.open(ws["workspaceId"])
        self.sid = self.session["sessionId"]

    def test_modes_cache_separately_and_cursors_bind_query(self):
        with patch("cadence_mcp.capture_objects.run_tcl", side_effect=worker) as native:
            first = query_objects(self.capture, self.sid, "connections", "wire", None, None, 1)
            self.assertFalse(first["complete"])
            second = query_objects(self.capture, self.sid, "connections", "wire", None, first["nextCursor"], 1)
            self.assertEqual(second["items"][0]["objectId"], "w2")
            self.assertEqual(native.call_count, 1)
            graphic = query_objects(self.capture, self.sid, "graphics", "graphic", "p", None, 100)
            self.assertEqual(graphic["items"][0]["attributes"]["text"], "说明\n第二行")
            self.assertEqual(native.call_count, 2)
            for mode, kind, page, size in (("connections", "alias", None, 1), ("connections", "wire", "p", 1),
                                           ("connections", "wire", None, 2), ("graphics", "graphic", None, 1)):
                with self.assertRaises(CadenceError): query_objects(self.capture, self.sid, mode, kind, page, first["nextCursor"], size)
        directory = self.capture.workspaces[self.session["workspaceId"]]["directory"]
        self.assertFalse(list(directory.glob("page-objects-*.json")))

    def test_bad_scope_and_stale_snapshot_rejected_before_worker(self):
        with patch("cadence_mcp.capture_objects.run_tcl") as native:
            with self.assertRaises(CadenceError): query_objects(self.capture, self.sid, "connections", "wire", "unknown", None, 10)
            self.capture.sessions[self.sid]["design"].write_bytes(b"changed")
            with self.assertRaises(CadenceError): query_objects(self.capture, self.sid, "connections", "wire", None, None, 10)
            native.assert_not_called()

    def test_no_electrical_or_rendered_bounds_claim(self):
        with patch("cadence_mcp.capture_objects.run_tcl", worker):
            data = query_objects(self.capture, self.sid, "graphics", "display_property", None, None, 10)
        self.assertFalse(data["electricalConnectivityVerified"])
        self.assertEqual(data["displayBoundsSpace"], "native_cached_unverified")
        self.assertTrue(data["items"][0]["attributes"]["boundsDirty"])

    def test_mcp_queries_strict_input_and_partial(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                ws = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                def base_worker(config, script, args, cwd): Path(args[1]).write_text(json.dumps(design()), encoding="utf-8")
                with patch("cadence_mcp.capture.run_tcl", base_worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": ws.structured_content["data"]["workspaceId"]})
                sid = opened.structured_content["data"]["sessionId"]
                with patch("cadence_mcp.capture_objects.run_tcl", worker):
                    result = await client.call_tool("capture_query_connections", {"sessionId": sid, "entity": "wire", "limit": 1})
                    graphics = await client.call_tool("capture_query_graphics", {"sessionId": sid, "entity": "titleblock"})
                self.assertEqual(result.structured_content["status"], "partial")
                self.assertFalse(result.structured_content["evidence"]["complete"])
                self.assertFalse(graphics.is_error)
                self.assertTrue((await client.call_tool("capture_query_connections", {"sessionId": sid, "entity": "wire", "eval": "no"})).is_error)
        asyncio.run(exercise())
