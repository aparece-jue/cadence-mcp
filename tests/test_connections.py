import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from cadence_mcp.capture import CaptureService
from cadence_mcp.connections import compare_connections
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.server import create_server


def design():
    return {"schematic": [{"objectId": "s", "name": "main"}],
            "page": [{"objectId": "p", "schematicId": "s", "name": "page1"}],
            "part": [{"objectId": "u", "pageId": "p", "schematicId": "s", "reference": "U1"}],
            "pin": [{"objectId": "pin1", "partId": "u", "pageId": "p", "schematicId": "s",
                     "reference": "U1", "number": "1", "name": "IN", "connected": True, "net": "INPUT"},
                    {"objectId": "pin2", "partId": "u", "pageId": "p", "schematicId": "s",
                     "reference": "U1", "number": "2", "name": "NC", "connected": False, "net": ""}]}


def expectation(**changes):
    return {"schematicName": "main", "pageName": "page1", "reference": "U1", "pinNumber": "1",
            "connected": True, "net": "INPUT", **changes}


class ComparisonTests(unittest.TestCase):
    def test_selected_pass_does_not_pass_whole_design(self):
        report = compare_connections(design(), [expectation()], "fixture-spec@1")
        self.assertEqual(report["comparisonStatus"], "pass")
        self.assertEqual(report["uncheckedObservedPinCount"], 1)
        self.assertIsNone(report["designPassed"])
        self.assertFalse(report["electricalConnectivityVerified"])
        self.assertFalse(report["expectationSourceIndependentlyVerified"])

    def test_wrong_net_disconnected_and_missing_pin_are_failures(self):
        for changes in ({"net": "WRONG"}, {"connected": False, "net": None}, {"pinNumber": "99"}):
            report = compare_connections(design(), [expectation(**changes)], "fixture-spec@1")
            self.assertEqual(report["comparisonStatus"], "fail")
            self.assertTrue(report["comparisonComplete"])
        report = compare_connections(design(), [expectation(pinNumber="2", connected=False, net=None)], "spec")
        self.assertEqual(report["comparisonStatus"], "pass")

    def test_ambiguity_and_unnamed_connected_net_stay_unverified(self):
        doc = design()
        doc["pin"].append({**doc["pin"][0], "objectId": "another"})
        report = compare_connections(doc, [expectation()], "spec")
        self.assertEqual(report["findings"][0]["reason"], "ambiguous_pin_definition")
        self.assertFalse(report["comparisonComplete"])
        doc = design()
        doc["pin"][0]["net"] = ""
        report = compare_connections(doc, [expectation()], "spec")
        self.assertEqual(report["comparisonStatus"], "unverified")

    def test_names_are_exact_and_pages_are_separate(self):
        doc = design()
        doc["page"].append({"objectId": "p2", "schematicId": "s", "name": "page2"})
        doc["pin"].append({**doc["pin"][0], "objectId": "other", "pageId": "p2", "net": "OTHER"})
        self.assertEqual(compare_connections(doc, [expectation()], "spec")["comparisonStatus"], "pass")
        for changes in ({"reference": "U10"}, {"reference": "u1"}, {"pageName": "PAGE1"}, {"pinNumber": "01"}):
            self.assertEqual(compare_connections(doc, [expectation(**changes)], "spec")["comparisonStatus"], "fail")

    def test_empty_duplicate_contradictory_or_extra_expectations_rejected(self):
        for rows in ([], [expectation(), expectation()], [expectation(connected=True, net=None)],
                     [expectation(connected=False)], [expectation(connected=1)],
                     [expectation(net="")], [expectation(extra="eval")], [expectation(reference="")]):
            with self.assertRaises(CadenceError): compare_connections(design(), rows, "spec")
        with self.assertRaises(CadenceError): compare_connections(design(), [expectation()], "  ")

    def test_input_is_not_changed(self):
        doc, rows = design(), [expectation()]
        before = deepcopy((doc, rows))
        compare_connections(doc, rows, "spec")
        self.assertEqual((doc, rows), before)


class ServiceTests(unittest.TestCase):
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
        self.source.write_bytes(b"mocked native input")
        self.config = Config(install, root / "work", (inputs,))

    @staticmethod
    def worker(config, script, args, cwd):
        Path(args[1]).write_text(json.dumps(design()), encoding="utf-8")

    def test_report_hash_revision_and_stale_session(self):
        service = CaptureService(self.config)
        ws = service.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", self.worker):
            session = service.open(ws["workspaceId"])
        sid, revision = session["sessionId"], session["revision"]
        report = service.compare_connections(sid, revision, [expectation()], "fixture-spec@1")
        directory = service.workspaces[ws["workspaceId"]]["directory"]
        target = directory / report["artifact"]["workspaceRelativePath"]
        self.assertEqual(report["artifact"]["sha256"], sha256(target))
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["revision"], revision)
        for wrong in ("0" * 64, ""):
            with self.assertRaises(CadenceError): service.compare_connections(sid, wrong, [expectation()], "spec")
        (directory / "design.dsn").write_bytes(b"external change")
        with self.assertRaises(CadenceError): service.compare_connections(sid, revision, [expectation()], "spec")

    def test_mcp_strict_schema_partial_and_difference(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                created = await client.call_tool("cadence_create_workspace", {"sourceDesign": str(self.source)})
                with patch("cadence_mcp.capture.run_tcl", self.worker):
                    opened = await client.call_tool("capture_open", {"workspaceId": created.structured_content["data"]["workspaceId"]})
                args = {"sessionId": opened.structured_content["data"]["sessionId"],
                        "expectedRevision": opened.structured_content["data"]["revision"],
                        "expectations": [expectation()], "expectationSource": "fixture-spec@1"}
                checked = await client.call_tool("capture_compare_connections", args)
                self.assertFalse(checked.is_error)
                self.assertEqual(checked.structured_content["data"]["comparisonStatus"], "pass")
                different = await client.call_tool("capture_compare_connections", {**args, "expectations": [expectation(net="WRONG")]})
                self.assertFalse(different.is_error)  # Completed check with a domain failure.
                self.assertEqual(different.structured_content["data"]["comparisonStatus"], "fail")
                for changes in ({"extra": "eval"}, {"expectations": [expectation(extra="eval")]},
                                {"expectations": [expectation(connected=1)]}, {"expectations": []}):
                    bad = await client.call_tool("capture_compare_connections", {**args, **changes})
                    self.assertTrue(bad.is_error)
                ambiguous = design()
                ambiguous["pin"].append({**ambiguous["pin"][0], "objectId": "other"})
                with patch("cadence_mcp.capture.run_tcl", lambda config, script, args, cwd:
                           Path(args[1]).write_text(json.dumps(ambiguous), encoding="utf-8")):
                    second = await client.call_tool("capture_open", {"workspaceId": created.structured_content["data"]["workspaceId"]})
                partial = await client.call_tool("capture_compare_connections", {**args, "sessionId": second.structured_content["data"]["sessionId"]})
                self.assertEqual(partial.structured_content["status"], "partial")
                self.assertFalse(partial.structured_content["evidence"]["complete"])
        asyncio.run(exercise())
