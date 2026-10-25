from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from jsonschema import Draft202012Validator
from cadence_mcp.capture import CaptureService
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.server import create_server


def fake_worker(config, script, args, cwd):
    page = {"objectId": "s1/p1", "schematicId": "s1", "name": "页|{}\n\"\\"}
    parts = [{"objectId": f"part-{i}", "pageId": "s1/p1", "schematicId": "s1", "reference": ref}
             for i, ref in enumerate(("U1", "U10", "U1A"))]
    data = {"schematic": [{"objectId": "s1", "name": "电路"}], "page": [page], "part": parts, "pin": []}
    Path(args[1]).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return "", ""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        (self.install / "tcltk/bin").mkdir(parents=True)
        (self.install / "tcltk/bin/tclsh.exe").touch()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.source = self.inputs / "测试源.dsn"
        self.source.write_bytes(b"test input: native engine is mocked in unit tests")
        self.config = Config(self.install, self.root / "work", (self.inputs,))
        self.capture = CaptureService(self.config)

    def open_fixture(self):
        workspace = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", fake_worker):
            session = self.capture.open(workspace["workspaceId"])
        return workspace, session

    def query(self, sid, **kwargs):
        return self.capture.query(sid, kwargs.get("entity", "part"), kwargs.get("scope", {"kind": "design"}),
                                  kwargs.get("fields"), kwargs.get("reference"), kwargs.get("cursor"), kwargs.get("limit", 100))

    def test_copy_and_read_do_not_change_original(self):
        before = sha256(self.source)
        workspace, session = self.open_fixture()
        self.assertEqual(sha256(self.source), before)
        self.assertFalse(workspace["dependencyClosureVerified"])
        self.assertTrue(session["readOnly"])

    def test_exact_reference_and_unicode(self):
        _, session = self.open_fixture()
        rows = self.query(session["sessionId"], reference="U1")["items"]
        self.assertEqual([r["reference"] for r in rows], ["U1"])
        pages = self.query(session["sessionId"], entity="page")["items"]
        self.assertEqual(pages[0]["name"], "页|{}\n\"\\")

    def test_pagination_bound_to_query_and_session(self):
        _, session = self.open_fixture()
        sid = session["sessionId"]
        first = self.query(sid, limit=1)
        self.assertFalse(first["complete"])
        second = self.query(sid, limit=1, cursor=first["nextCursor"])
        self.assertEqual(second["items"][0]["reference"], "U10")
        with self.assertRaises(CadenceError):
            self.query(sid, cursor=first["nextCursor"], limit=2)
        _, another = self.open_fixture()
        with self.assertRaises(CadenceError):
            self.query(another["sessionId"], cursor=first["nextCursor"], limit=1)

    def test_changed_copy_invalidates_query_but_can_close(self):
        workspace, session = self.open_fixture()
        self.capture.workspaces[workspace["workspaceId"]]["directory"].joinpath("design.dsn").write_bytes(b"changed")
        with self.assertRaises(CadenceError) as error:
            self.query(session["sessionId"])
        self.assertEqual(error.exception.code, "target_changed")
        self.assertTrue(self.capture.close(session["sessionId"])["closed"])
        with self.assertRaises(CadenceError):
            self.query(session["sessionId"])

    def test_unknown_page_field_and_occurrence_rejected(self):
        _, session = self.open_fixture()
        for arguments in ({"fields": ["unknown"]}, {"scope": {"kind": "page", "pageId": "missing"}},
                          {"scope": {"kind": "occurrence", "occurrencePath": []}}):
            with self.assertRaises(CadenceError): self.query(session["sessionId"], **arguments)

    def test_outside_and_relative_paths_rejected(self):
        outside = self.root / "outside.dsn"
        outside.touch()
        for value in (str(outside), "inputs/test.dsn", str(self.inputs / "../outside.dsn")):
            with self.assertRaises(CadenceError): self.capture.create_workspace(value)

    def test_resolved_source_symlink_cannot_escape_root(self):
        outside = self.root / "outside.dsn"
        outside.touch()
        link = self.inputs / "link.dsn"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink privilege is unavailable")
        with self.assertRaises(CadenceError): self.capture.create_workspace(str(link))

    def test_snapshot_is_bound_and_does_not_claim_validation(self):
        workspace, session = self.open_fixture()
        snapshot = self.capture.snapshot(session["sessionId"])
        directory = self.capture.workspaces[workspace["workspaceId"]]["directory"]
        self.assertEqual(snapshot["artifact"]["sha256"], sha256(directory / snapshot["artifact"]["workspaceRelativePath"]))
        self.assertEqual(snapshot["artifact"]["validationState"], "unverified")

    def test_malformed_worker_result_and_crash_do_not_create_sessions(self):
        workspace = self.capture.create_workspace(str(self.source))
        def broken(config, script, args, cwd):
            Path(args[1]).write_text('{"part":[]}', encoding="utf-8")
        with patch("cadence_mcp.capture.run_tcl", broken), self.assertRaises(CadenceError):
            self.capture.open(workspace["workspaceId"])
        with patch("cadence_mcp.capture.run_tcl", side_effect=CadenceError("worker_crashed", "crash")), self.assertRaises(CadenceError):
            self.capture.open(workspace["workspaceId"])
        self.assertEqual(self.capture.sessions, {})

    def test_wiring_mcp_linear_coverage_and_errors(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                missing = await client.call_tool("capture_check_wiring", {"sessionId": "missing"})
                self.assertTrue(missing.is_error)
                created = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", fake_worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": created.structured_content["data"]["workspaceId"]})
                sid = opened.structured_content["data"]["sessionId"]
                def diagonal(config, script, args, cwd):
                    Path(args[1]).write_text(json.dumps({"schematic": [], "page": [{"objectId": "p"}], "wire": [
                        {"objectId": "w", "pageId": "p", "net": "A", "points": [[0,0],[10,10]]}
                    ]}), encoding="utf-8")
                with patch("cadence_mcp.capture.run_tcl", diagonal):
                    checked = await client.call_tool("capture_check_wiring", {"sessionId": sid})
                self.assertFalse(checked.is_error)
                self.assertEqual(checked.structured_content["status"], "succeeded")
                self.assertTrue(checked.structured_content["evidence"]["complete"])
                self.assertTrue(checked.structured_content["data"]["geometryComplete"])
                self.assertEqual(checked.structured_content["data"]["geometryCoverage"], "bounded_linear_wire_intersections")
                self.assertFalse(checked.structured_content["data"]["electricalConnectivityVerified"])
                self.assertIsNone(checked.structured_content["data"]["designPassed"])
                self.assertIn("grid_alignment", checked.structured_content["data"]["notChecked"])
                extra = await client.call_tool("capture_check_wiring", {"sessionId": sid, "eval": "bad"})
                self.assertTrue(extra.is_error)
        asyncio.run(exercise())

    def test_wiring_report_revision_and_worker_failures(self):
        workspace, session = self.open_fixture()
        sid = session["sessionId"]
        def geometry_worker(config, script, args, cwd):
            self.assertEqual(script, "inspect_geometry.tcl")
            Path(args[1]).write_text(json.dumps({"schematic": [], "page": [{"objectId": "p"}], "wire": [
                {"objectId": "w", "pageId": "p", "net": "A", "points": [[0,0],[10,0]]}
            ]}), encoding="utf-8")
        with patch("cadence_mcp.capture.run_tcl", geometry_worker):
            report = self.capture.check_wiring(sid)
        self.assertFalse(report["pdfRequired"])
        self.assertFalse(report["electricalConnectivityVerified"])
        self.assertEqual(report["revision"], session["revision"])
        path = self.capture.workspaces[workspace["workspaceId"]]["directory"] / report["artifact"]["workspaceRelativePath"]
        self.assertEqual(sha256(path), report["artifact"]["sha256"])
        with patch("cadence_mcp.capture.run_tcl", fake_worker), self.assertRaises(CadenceError):
            self.capture.check_wiring(sid)
        self.capture.sessions[sid]["design"].write_bytes(b"changed")
        with self.assertRaises(CadenceError) as error:
            self.capture.check_wiring(sid)
        self.assertEqual(error.exception.code, "target_changed")

    def test_installation_workspace_overlap_rejected(self):
        with self.assertRaises(ValueError): Config(self.install, self.install / "output", (self.inputs,))

    def test_mcp_schema_calls_errors_and_extra_fields(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                tools = (await client.list_tools()).tools
                self.assertEqual(len(tools), 193)
                binding_tool=next(t for t in tools if t.name=='capture_query_cache_binding')
                self.assertTrue(binding_tool.model_dump(mode='json',by_alias=True)['annotations']['readOnlyHint'])
                self.assertEqual(set(binding_tool.input_schema['required']),{'sessionId','partId'})
                for tool in tools:
                    self.assertFalse(tool.input_schema.get("additionalProperties", True))
                    self.assertIsNotNone(tool.output_schema)
                    Draft202012Validator.check_schema(tool.input_schema)
                    Draft202012Validator.check_schema(tool.output_schema)
                capabilities = await client.call_tool("cadence_get_capabilities", {})
                self.assertFalse(capabilities.is_error)
                schema = next(t.output_schema for t in tools if t.name == "cadence_get_capabilities")
                Draft202012Validator(schema).validate(capabilities.structured_content)
                self.assertEqual(capabilities.structured_content["data"]["features"]["pspice.run"], "experimental_independent_engine_tcl")
                failed = await client.call_tool("capture_close", {"sessionId": "missing"})
                self.assertTrue(failed.is_error)
                self.assertEqual(failed.structured_content["error"]["code"], "session_lost")
                extra = await client.call_tool("cadence_get_capabilities", {"exec": "malicious"})
                self.assertTrue(extra.is_error)
                created = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                wid = created.structured_content["data"]["workspaceId"]
                with patch("cadence_mcp.capture.run_tcl", fake_worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": wid})
                sid = opened.structured_content["data"]["sessionId"]
                page = await client.call_tool("capture_query", {"sessionId": sid, "entity": "part", "scope": {"kind": "design"}, "limit": 1})
                self.assertFalse(page.is_error)
                self.assertEqual(page.structured_content["status"], "partial")
                self.assertFalse(page.structured_content["evidence"]["complete"])
                unsupported = await client.call_tool("capture_query", {"sessionId": sid, "entity": "pin", "scope": {"kind": "occurrence"}})
                self.assertTrue(unsupported.is_error)
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()


