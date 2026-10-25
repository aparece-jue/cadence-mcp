import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import CapturePropertyEdits, definition_baseline
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.gui_jobs import durable_json
from cadence_mcp.isolated_jobs import IsolatedJobs, digest
from test_readonly import fake_worker


class FixtureJobs(IsolatedJobs):
    kind = "fixture"

    def __init__(self, config):
        super().__init__(config)
        self.calls = 0
        self.mode = "normal"
        self.ready = threading.Event()

    def preview(self, payload):
        return payload

    def preflight(self, payload):
        if payload.get("reject"):
            raise CadenceError("target_changed", "fixture preflight failure")

    def execute(self, directory, payload, cancel, started):
        self.calls += 1
        started(123456789)
        (directory / "artifact.txt").write_text(payload["value"], encoding="utf-8")
        self.ready.set()
        if self.mode == "wait":
            cancel.wait(5)
            return {"state": "cancelled", "returnCode": 1}
        if self.mode == "lost_receipt":
            raise CadenceError("receipt_lost", "fixture save receipt loss")
        return {"state": "exited", "returnCode": 0}

    def verify(self, directory, payload, native_completed):
        target = directory / "artifact.txt"
        if target.read_text(encoding="utf-8") != payload["value"]:
            raise CadenceError("verification_failed", "fixture artifact mismatch")
        return {"state": "verified" if native_completed else "verified_recovered",
                "nativeCompletionVerified": native_completed,
                "artifact": {"workspaceRelativePath": "artifact.txt", "sha256": sha256(target)}}


class IsolatedJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install = self.root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.config = Config(install, self.root / "work", (self.inputs,))
        self.jobs = FixtureJobs(self.config)

    def plan(self, **payload):
        return self.jobs.create_plan({"value": "planned value", **payload})

    def test_verified_idempotence_survives_new_service_and_output_tampering(self):
        plan = self.plan()
        first = self.jobs.apply(plan["planId"], plan["planDigest"], "key")
        fresh = FixtureJobs(self.config)
        self.assertEqual(first, fresh.apply(plan["planId"], plan["planDigest"], "key"))
        self.assertEqual(self.jobs.calls, 1)
        self.assertEqual(fresh.calls, 0)
        directory, _, _ = fresh._load(plan["planId"])
        (directory / "artifact.txt").write_text("external change", encoding="utf-8")
        with self.assertRaises(CadenceError) as error: fresh.apply(plan["planId"], plan["planDigest"], "key")
        self.assertEqual(error.exception.code, "target_changed")
        self.assertEqual(fresh.calls, 0)

    def test_digest_key_conflicts_and_started_never_replay(self):
        first, second = self.plan(), self.plan(value="other")
        with self.assertRaises(CadenceError): self.jobs.apply(first["planId"], "bad", "key")
        self.jobs.apply(first["planId"], first["planDigest"], "key")
        with self.assertRaises(CadenceError) as error: self.jobs.apply(second["planId"], second["planDigest"], "key")
        self.assertEqual(error.exception.code, "idempotency_conflict")
        with self.assertRaises(CadenceError): self.jobs.apply(first["planId"], first["planDigest"], "different")
        directory, path, row = self.jobs._load(second["planId"])
        row["state"] = "started"
        durable_json(path, row)
        with self.assertRaises(CadenceError) as error: self.jobs.apply(second["planId"], second["planDigest"], "second-key")
        self.assertEqual(error.exception.code, "write_not_replayed")
        self.assertEqual(self.jobs.calls, 1)

    def test_preflight_rejects_before_claim_or_native_side_effect(self):
        plan = self.plan(reject=True)
        with self.assertRaises(CadenceError): self.jobs.apply(plan["planId"], plan["planDigest"], "key")
        self.assertEqual(self.jobs.calls, 0)
        self.assertEqual(self.jobs.jobs()["jobs"][0]["state"], "planned")
        self.assertFalse(list(self.jobs.root.glob("key-*.json")))

    def test_pending_cancel_and_live_cancel_are_durable(self):
        pending = self.plan()
        self.assertEqual(self.jobs.cancel(pending["planId"], pending["planDigest"])["state"], "cancelled")
        with self.assertRaises(CadenceError): self.jobs.apply(pending["planId"], pending["planDigest"], "key")
        active = self.plan()
        self.jobs.mode = "wait"
        errors = []
        def apply():
            try: self.jobs.apply(active["planId"], active["planDigest"], "active-key")
            except CadenceError as error: errors.append(error.code)
        worker = threading.Thread(target=apply)
        worker.start()
        self.assertTrue(self.jobs.ready.wait(2))
        self.assertTrue(self.jobs.cancel(active["planId"], active["planDigest"])["cancelRequested"])
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, ["operation_cancelled"])
        self.assertEqual(self.jobs._load(active["planId"])[2]["state"], "cancelled")

    def test_recovery_verifies_existing_artifact_without_reapplying(self):
        plan = self.plan()
        self.jobs.mode = "lost_receipt"
        with self.assertRaises(CadenceError): self.jobs.apply(plan["planId"], plan["planDigest"], "key")
        fresh = FixtureJobs(self.config)
        with patch("cadence_mcp.isolated_jobs.process_status", return_value="running"):
            with self.assertRaises(CadenceError): fresh.recover(plan["planId"], plan["planDigest"])
        with patch("cadence_mcp.isolated_jobs.process_status", return_value="stopped"):
            result = fresh.recover(plan["planId"], plan["planDigest"])
        self.assertEqual(result["state"], "verified_recovered")
        self.assertFalse(result["nativeCompletionVerified"])
        self.assertFalse(result["mutationReplayed"])
        self.assertEqual(fresh.calls, 0)

    def test_expired_and_tampered_records_and_path_ids(self):
        plan = self.plan()
        _, path, row = self.jobs._load(plan["planId"])
        row["plan"]["expiresAt"] = time.time() - 1
        row["digest"] = digest(row["plan"])
        durable_json(path, row)
        with self.assertRaises(CadenceError) as error: self.jobs.apply(plan["planId"], row["digest"], "key")
        self.assertEqual(error.exception.code, "plan_expired")
        row["plan"]["payload"]["value"] = "tampered"
        durable_json(path, row)
        with self.assertRaises(CadenceError): self.jobs._load(plan["planId"])
        with self.assertRaises(CadenceError): self.jobs._load("../escape")

    def test_listing_pages_and_unknown_queries(self):
        self.plan(value="one")
        self.plan(value="two")
        first = self.jobs.jobs(0, 1)
        self.assertEqual(first["total"], 2)
        self.assertEqual(first["nextOffset"], 1)
        self.assertNotEqual(first["jobs"][0]["planId"], self.jobs.jobs(1, 1)["jobs"][0]["planId"])
        for args in ((-1, 1), (0, 0), (0, 101)):
            with self.assertRaises(CadenceError): self.jobs.jobs(*args)


class CaptureEditPlanningTests(unittest.TestCase):
    def setUp(self):
        IsolatedJobTests.setUp(self)
        self.source = self.inputs / "fixture.dsn"
        self.source.write_bytes(b"mock design")
        self.capture = CaptureService(self.config)
        self.ws = self.capture.create_workspace(str(self.source))
        with patch("cadence_mcp.capture.run_tcl", fake_worker):
            self.session = self.capture.open(self.ws["workspaceId"])
        self.editor = CapturePropertyEdits(self.config, self.capture)

    def test_property_plan_has_explicit_before_after_and_unchanged_baseline(self):
        props = {"schematicName": "电路", "pageName": "页", "reference": "U1", "items": [{"name": "Value", "value": "1k"}]}
        graph=[{'scope':['电路','页',ref],'properties':[{'name':'Value','value':'1k'}]} for ref in ('U1','U10','U1A')]
        with patch("cadence_mcp.capture_edit.read_part_properties", return_value=props), patch('cadence_mcp.capture_edit.read_design_properties',return_value=graph):
            plan = self.editor.plan(self.session["sessionId"], "part-0", "Value", "2k")
        payload=self.editor._load(plan['planId'])[2]['plan']['payload']
        self.assertIn('expectedPropertySnapshotDigest',payload)
        self.assertEqual(graph[0]['properties'][0]['value'],'1k')
        self.assertEqual(plan["preview"]["oldValue"], "1k")
        self.assertEqual(plan["preview"]["value"], "2k")
        self.assertFalse(plan["sourceWillBeModified"])
        self.assertTrue(plan["planDigest"])
        self.capture.sessions[self.session["sessionId"]]["design"].write_bytes(b"changed")
        with self.assertRaises(CadenceError) as error: self.editor.apply(plan["planId"], plan["planDigest"], "key")
        self.assertEqual(error.exception.code, "target_changed")

    def test_invalid_property_missing_or_ambiguous_target_rejected(self):
        sid = self.session["sessionId"]
        for property_name, value in (("Implementation", "anything"), ("Value", "x\x00y"), ("Value", "x" * 1025)):
            with self.assertRaises(CadenceError): self.editor.plan(sid, "part-0", property_name, value)
        with self.assertRaises(CadenceError): self.editor.plan(sid, "foreign", "Value", "2k")
        data = self.capture.sessions[sid]["data"]
        data["part"].append({**data["part"][0], "objectId": "unit2"})
        with self.assertRaises(CadenceError) as error: self.editor.plan(sid, "part-0", "Value", "2k")
        self.assertEqual(error.exception.code, "ambiguous_target")

    def test_baseline_is_order_independent_and_detects_node_change(self):
        from test_connections import design
        data = design()
        before = definition_baseline(data)
        data["pin"].reverse()
        self.assertEqual(definition_baseline(data), before)
        data["pin"][0]["net"] = "unexpected"
        self.assertNotEqual(definition_baseline(data), before)
