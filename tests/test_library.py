import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.library import LibraryService, validate_library
from cadence_mcp.server import create_server


def document():
    data = {key: [] for key in ("package", "device", "cell", "part", "pin")}
    for i in (1, 2):
        p, d, c, part = f"p{i}", f"d{i}", f"c{i}", f"part{i}"
        data["package"].append({"objectId": p, "name": f"R{i}", "size": 1, "homogeneous": True, "footprint": ""})
        data["device"].append({"objectId": d, "packageId": p, "designator": "A", "position": i, "cellId": c})
        data["cell"].append({"objectId": c, "deviceId": d, "packageId": p, "name": "单元|{}\n"})
        data["part"].append({"objectId": part, "deviceId": d, "cellId": c, "packageId": p, "name": "R"})
        data["pin"].append({"objectId": f"pin{i}", "partId": part, "deviceId": d, "packageId": p,
                            "name": "端子", "position": 0, "number": str(i + 10), "pinType": 5,
                            "visible": True, "shared": False, "swapId": 0, "hotSpot": [0, i * 10]})
    return data


def worker(config, script, args, cwd):
    assert script == "inspect_library.tcl"
    Path(args[1]).write_text(json.dumps(document(), ensure_ascii=False), encoding="utf-8")


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install = self.root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        inputs = self.root / "input"
        inputs.mkdir()
        self.source = inputs / "中文.olb"
        self.source.write_bytes(b"mocked library")
        self.config = Config(install, self.root / "work", (inputs,))
        self.library = LibraryService(self.config)

    def open(self):
        with patch("cadence_mcp.library.run_tcl", worker):
            return self.library.open(str(self.source))

    def test_read_copy_unicode_mapping_and_immutable_source(self):
        before = sha256(self.source)
        opened = self.open()
        result = self.library.query(opened["libraryId"], "pin", "R1", None, 100)
        self.assertEqual(result["items"][0]["number"], "11")
        self.assertEqual(result["items"][0]["position"], 0)
        self.assertEqual(result["items"][0]["name"], "端子")
        self.assertEqual(opened["counts"], {key: 2 for key in document()})
        self.assertEqual(sha256(self.source), before)
        self.assertFalse(opened["externalFootprintVerified"])
        self.assertTrue(opened["readOnly"])

    def test_query_page_cursor_exact_name_and_closed_session(self):
        lid = self.open()["libraryId"]
        first = self.library.query(lid, "package", None, None, 1)
        self.assertFalse(first["complete"])
        self.assertEqual(self.library.query(lid, "package", None, first["nextCursor"], 1)["items"][0]["name"], "R2")
        for entity, name, limit in (("pin", None, 1), ("package", "R1", 1), ("package", None, 2)):
            with self.assertRaises(CadenceError): self.library.query(lid, entity, name, first["nextCursor"], limit)
        other = self.open()["libraryId"]
        with self.assertRaises(CadenceError): self.library.query(other, "package", None, first["nextCursor"], 1)
        for name in ("r1", "R", "R10"):
            self.assertEqual(self.library.query(lid, "package", name, None, 100)["items"], [])
        self.library.close(lid)
        with self.assertRaises(CadenceError): self.library.query(lid, "package", None, None, 10)

    def test_stale_copy_rejected_but_close_releases(self):
        lid = self.open()["libraryId"]
        (self.library.sessions[lid]["directory"] / "library.olb").write_bytes(b"changed")
        with self.assertRaises(CadenceError) as error:
            self.library.query(lid, "pin", None, None, 100)
        self.assertEqual(error.exception.code, "target_changed")
        self.assertTrue(self.library.close(lid)["closed"])

    def test_path_extension_worker_failure_and_bounded_queries(self):
        outside = self.root / "outside.olb"
        outside.touch()
        for path in (str(outside), "relative.olb"):
            with self.assertRaises(CadenceError): self.library.open(path)
        wrong = self.source.with_suffix(".dsn")
        wrong.touch()
        with self.assertRaises(CadenceError): self.library.open(str(wrong))
        with patch("cadence_mcp.library.run_tcl", side_effect=CadenceError("worker_crashed", "fixture")):
            with self.assertRaises(CadenceError): self.library.open(str(self.source))
        self.assertFalse(self.library.sessions)
        lid = self.open()["libraryId"]
        for entity, limit in (("shell", 1), ("pin", 0), ("pin", 1001), ("pin", True)):
            with self.assertRaises(CadenceError): self.library.query(lid, entity, None, None, limit)

    def test_bad_shapes_types_duplicates_and_parent_mappings(self):
        bad = [{}, [], {**document(), "extra": []}]
        for key, value in (("number", 1), ("position", True), ("hotSpot", [1, 2.0]),
                           ("hotSpot", [1]), ("visible", 1), ("partId", "missing"),
                           ("deviceId", "d2"), ("packageId", "p2"), ("objectId", "p1")):
            row = document()
            row["pin"][0][key] = value
            bad.append(row)
        for kind, key, value in (("cell", "deviceId", "d2"), ("part", "cellId", "c2"),
                                 ("device", "cellId", "missing"), ("package", "size", "1")):
            row = document()
            row[kind][0][key] = value
            bad.append(row)
        for row in bad:
            with self.assertRaises(CadenceError): validate_library(row)

    def test_bad_worker_result_does_not_register_session(self):
        for payload in ("{}", "[1]", "x", "x" * (32 * 1024 * 1024 + 1)):
            def invalid(config, script, args, cwd):
                Path(args[1]).write_text(payload, encoding="utf-8")
            with patch("cadence_mcp.library.run_tcl", invalid), self.assertRaises(CadenceError):
                self.library.open(str(self.source))
        self.assertFalse(self.library.sessions)

    def test_input_validator_does_not_modify_observations(self):
        data = document()
        expected = deepcopy(data)
        validate_library(data)
        self.assertEqual(data, expected)

    def test_library_mcp_strict_inputs_partial_and_capabilities(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                with patch("cadence_mcp.library.run_tcl", worker):
                    opened = await client.call_tool("capture_library_open", {"sourceLibrary": str(self.source)})
                self.assertFalse(opened.is_error)
                lid = opened.structured_content["data"]["libraryId"]
                result = await client.call_tool("capture_library_query", {"libraryId": lid, "entity": "pin", "limit": 1})
                self.assertEqual(result.structured_content["status"], "partial")
                self.assertFalse(result.structured_content["evidence"]["complete"])
                extra = await client.call_tool("capture_library_query", {"libraryId": lid, "entity": "pin", "eval": "no"})
                self.assertTrue(extra.is_error)
                caps = await client.call_tool("cadence_get_capabilities", {})
                self.assertEqual(caps.structured_content["data"]["features"]["capture.olb"], "experimental_read_only")
                self.assertFalse((await client.call_tool("capture_library_close", {"libraryId": lid})).is_error)
        asyncio.run(exercise())
