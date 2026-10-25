import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_user_properties import CaptureUserProperties, check_name
from cadence_mcp.core import CadenceError, Config
from cadence_mcp.server import create_server
from test_connections import design


def layers(user=None, effective=None):
    return {"partId": "u", "schematicName": "main", "pageName": "page1", "reference": "U1",
            "user": [{"name": "Other", "value": "keep"}] + (user or []),
            "effective": [{"name": "Color", "value": "48"}, {"name": "Manufacturer", "value": "library"}] + (effective or []),
            "display": []}


def worker(config, script, args, cwd):
    Path(args[1]).write_text(json.dumps(design()), encoding="utf-8")


class UserPropertyTests(unittest.TestCase):
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
        self.editor = CaptureUserProperties(self.config, self.capture)

    def plan(self, name="MCP_MPN", operation="set", value="value", fallback=None, before=None):
        with patch("cadence_mcp.capture_user_properties.read_property_layers", return_value=before or layers()):
            return self.editor.plan(self.sid, "u", operation, name, value, fallback)

    def test_create_empty_update_and_delete_are_distinct_explicit_plans(self):
        created = self.plan(value="")
        self.assertFalse(created["preview"]["oldUserExists"])
        self.assertEqual(created["preview"]["expectedEffectiveAfter"], "")
        before = layers(user=[{"name": "MCP_MPN", "value": ""}], effective=[{"name": "MCP_MPN", "value": ""}])
        deleted = self.plan(operation="delete", value=None, fallback=None, before=before)
        self.assertTrue(deleted["preview"]["oldUserExists"])
        self.assertEqual(deleted["preview"]["oldUserValue"], "")
        self.assertIsNone(deleted["preview"]["expectedEffectiveAfter"])

    def test_protected_names_inherited_attributes_case_and_ambiguous_targets_rejected(self):
        for name in ("Value", "PCB Footprint", "Source Library", "PSpiceTemplate", "Reference", "Pin Type", "Net Alias", " Name", "bad\nname"):
            with self.assertRaises(CadenceError): self.plan(name=name)
        with self.assertRaises(CadenceError): self.plan(name="Color")
        self.assertTrue(self.plan(name="Manufacturer")["planId"])
        before = layers(user=[{"name": "mpn", "value": "old"}])
        with self.assertRaises(CadenceError): self.plan(name="MPN", before=before)
        self.capture.sessions[self.sid]["data"]["part"].append({**design()["part"][0], "objectId": "other-unit"})
        with self.assertRaises(CadenceError): self.plan()

    def test_invalid_operation_value_missing_user_delete_and_stale_source(self):
        for kwargs in ({"operation": "eval"}, {"operation": "delete", "value": "wrong"}, {"value": None},
                       {"value": "x\x00y"}, {"value": "x" * 1025}, {"fallback": "irrelevant"}):
            with self.assertRaises(CadenceError): self.plan(**kwargs)
        with self.assertRaises(CadenceError): self.plan(operation="delete", value=None)
        planned = self.plan()
        self.capture.sessions[self.sid]["design"].write_bytes(b"changed")
        with self.assertRaises(CadenceError) as error: self.editor.apply(planned["planId"], planned["planDigest"], "key")
        self.assertEqual(error.exception.code, "target_changed")

    def test_independent_fallback_expected_is_not_replaced_with_observation(self):
        before = layers(user=[{"name": "Manufacturer", "value": "override"}])
        plan = self.plan(name="Manufacturer", operation="delete", value=None, fallback="library", before=before)
        directory, _, row = self.editor._load(plan["planId"])
        (directory / "design.dsn").write_bytes(b"mock independent output")
        with patch("cadence_mcp.capture.run_tcl", worker), patch("cadence_mcp.capture_user_properties.read_property_layers", return_value=layers()):
            result = self.editor.verify(directory, row["plan"]["payload"], native_completed=False)
        self.assertEqual(result["observedEffectiveValue"], "library")
        self.assertFalse(result["userPropertyExists"])
        wrong = {**row["plan"]["payload"], "expectedEffectiveAfter": None}
        with patch("cadence_mcp.capture.run_tcl", worker), patch("cadence_mcp.capture_user_properties.read_property_layers", return_value=layers()):
            with self.assertRaises(CadenceError) as error: self.editor.verify(directory, wrong, native_completed=False)
        self.assertEqual(error.exception.code, "effective_fallback_mismatch")

    def test_verification_rejects_unrelated_user_property_change(self):
        plan = self.plan()
        directory, _, row = self.editor._load(plan["planId"])
        (directory / "design.dsn").write_bytes(b"mock output")
        after = layers(user=[{"name": "MCP_MPN", "value": "value"}], effective=[{"name": "MCP_MPN", "value": "value"}])
        after["user"][0]["value"] = "unexpected"
        with patch("cadence_mcp.capture.run_tcl", worker), patch("cadence_mcp.capture_user_properties.read_property_layers", return_value=after):
            with self.assertRaises(CadenceError) as error: self.editor.verify(directory, row["plan"]["payload"], native_completed=False)
        self.assertEqual(error.exception.code, "unexpected_property_change")

    def test_pending_output_cannot_be_opened_and_fixed_command_has_no_shell(self):
        plan = self.plan()
        with self.assertRaises(CadenceError) as error: self.editor.open_output(plan["planId"], plan["planDigest"])
        self.assertEqual(error.exception.code, "output_unverified")
        directory, _, row = self.editor._load(plan["planId"])
        argv = self.editor.native_command(directory, row["plan"]["payload"])
        self.assertEqual(Path(argv[1]).name, "edit_user_property.tcl")
        self.assertIn("MCP_MPN", argv)
        self.assertIn("set", argv)

    def test_mcp_plan_cancel_jobs_and_strict_values(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                ws = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": ws.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"], "partId": "u", "operation": "set", "propertyName": "MPN", "value": "demo"}
                with patch("cadence_mcp.capture_user_properties.read_property_layers", return_value=layers()):
                    planned = await client.call_tool("capture_plan_user_property", args)
                self.assertFalse(planned.is_error)
                plan = planned.structured_content["data"]
                self.assertTrue((await client.call_tool("capture_open_edit_result", {"planId": plan["planId"], "planDigest": plan["planDigest"], "kind": "user_property"})).is_error)
                self.assertFalse((await client.call_tool("capture_cancel_user_property", {"planId": plan["planId"], "planDigest": plan["planDigest"]})).is_error)
                jobs = await client.call_tool("capture_user_property_jobs", {})
                self.assertEqual(jobs.structured_content["data"]["jobs"][0]["state"], "cancelled")
                self.assertTrue((await client.call_tool("capture_plan_user_property", {**args, "exec": "no"})).is_error)
        asyncio.run(exercise())
