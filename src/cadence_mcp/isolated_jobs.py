"""Durable plans for fixed operations whose output is a new owned artifact.

Never mutates a source workspace, never replays a started operation. Native
workers use kill-on-close process trees; recovery only verifies existing bytes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

from .bridge_diagnostics import process_status
from .core import CadenceError, checked_path, sha256
from .gui_jobs import acquire_guard, durable_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class IsolatedJobs:
    kind = None
    max_record_bytes = 65536

    def __init__(self, config):
        self.config = config
        if not isinstance(self.kind, str) or not re.fullmatch(r"[a-z_]+", self.kind):
            raise ValueError("A fixed internal job kind is required")
        parent = config.workspace_root / "isolated-jobs"
        parent.mkdir(exist_ok=True)
        checked_path(str(parent), (config.workspace_root,))
        root = parent / self.kind
        root.mkdir(exist_ok=True)
        self.root = checked_path(str(root), (config.workspace_root,))
        self.events = {}
        self.event_lock = threading.Lock()
        self.apply_lock = threading.RLock()

    def _guard(self):
        checked_path(str(self.root), (self.config.workspace_root,))
        return acquire_guard(self.root)

    def create_plan(self, payload):
        with self.apply_lock:
            guard = self._guard()
            try:
                if sum(1 for _ in self.root.glob("plan-*")) >= 4096:
                    raise CadenceError("plan_limit", "Too many durable plans in this workspace.")
                plan_id = uuid.uuid4().hex
                directory = self.root / f"plan-{plan_id}"
                directory.mkdir()
                checked_path(str(directory), (self.root,))
                now = time.time()
                plan = {"schemaVersion": "1.0", "planId": plan_id, "kind": self.kind,
                        "createdAt": now, "expiresAt": now + 900, "payload": payload}
                row = {"plan": plan, "digest": digest(plan), "state": "planned", "idempotencyKeyHash": None}
                durable_json(directory / "plan.json", row)
                return {"planId": plan_id, "planDigest": row["digest"], "state": "planned",
                        "expiresAt": plan["expiresAt"], "preview": self.preview(payload),
                        "sourceWillBeModified": False, "outputMode": "new_isolated_copy"}
            finally:
                guard.close()

    def _load(self, plan_id):
        if not isinstance(plan_id, str) or not re.fullmatch(r"[a-f0-9]{32}", plan_id):
            raise CadenceError("invalid_plan", "Invalid isolated plan identity.")
        directory = checked_path(str(self.root / f"plan-{plan_id}"), (self.root,))
        path = checked_path(str(directory / "plan.json"), (directory,))
        try:
            if path.stat().st_size > self.max_record_bytes:
                raise ValueError("Plan record exceeds limit")
            row = json.loads(path.read_text(encoding="utf-8"))
            if row["plan"]["planId"] != plan_id or row["plan"]["kind"] != self.kind or digest(row["plan"]) != row["digest"]:
                raise ValueError("Plan identity/digest/kind mismatch")
            if not isinstance(row["state"], str):
                raise ValueError("Invalid plan state")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CadenceError("invalid_plan", "Isolated plan record is invalid.") from error
        return directory, path, row

    def _verified_result(self, directory, row):
        result = row["result"]
        artifact = result["artifact"]
        target = checked_path(str(directory / artifact["workspaceRelativePath"]), (directory,))
        if sha256(target) != artifact["sha256"]:
            raise CadenceError("target_changed", "Previously verified output artifact changed.")
        return {**result, "mutationReplayed": False}

    def apply(self, plan_id, plan_digest, idempotency_key):
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
            raise CadenceError("invalid_idempotency_key", "A bounded idempotency key is required.")
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        with self.apply_lock:
            guard = self._guard()
            event = None
            try:
                directory, path, row = self._load(plan_id)
                if row["digest"] != plan_digest:
                    raise CadenceError("plan_digest_mismatch", "Plan digest does not match.")
                claim = self.root / f"key-{key_hash}.json"
                if claim.exists():
                    claim = checked_path(str(claim), (self.root,))
                    if claim.stat().st_size > 4096:
                        raise CadenceError("invalid_plan", "Invalid idempotency record.")
                    previous = json.loads(claim.read_text(encoding="utf-8"))
                    if previous != {"planId": plan_id, "planDigest": plan_digest, "kind": self.kind}:
                        raise CadenceError("idempotency_conflict", "Key was already used for another plan.")
                if row["idempotencyKeyHash"] is not None and row["idempotencyKeyHash"] != key_hash:
                    raise CadenceError("idempotency_conflict", "This plan is already bound to another key.")
                if row["state"] in {"verified", "verified_recovered"}:
                    return self._verified_result(directory, row)
                if row["state"] != "planned":
                    raise CadenceError("write_not_replayed", "Plan already started or terminated; inspect/recover it, never replay the mutation.")
                if time.time() > row["plan"]["expiresAt"]:
                    raise CadenceError("plan_expired", "Prepare a new plan from a fresh snapshot.")
                self.preflight(row["plan"]["payload"])
                if not claim.exists():
                    durable_json(claim, {"planId": plan_id, "planDigest": plan_digest, "kind": self.kind})
                row.update(state="started", idempotencyKeyHash=key_hash, executorPid=os.getpid(), workerPid=None, startedAt=time.time())
                durable_json(path, row)  # Durable before any target copy or native invocation.
                event = threading.Event()
                with self.event_lock:
                    self.events[plan_id] = event

                def started(pid):
                    row["workerPid"] = pid
                    durable_json(path, row)  # Worker is still suspended until this succeeds.

                try:
                    process = self.execute(directory, row["plan"]["payload"], event, started)
                    row["process"] = process
                    if process["state"] == "cancelled":
                        row["state"] = "cancelled"
                        durable_json(path, row)
                        raise CadenceError("operation_cancelled", "Owned operation stopped; source was not modified.", "worker")
                    if process["state"] != "exited":
                        raise CadenceError("timeout", "Owned native operation timed out; its process tree stopped.", "worker")
                    if process["returnCode"] != 0:
                        raise self.worker_error(directory, row["plan"]["payload"], process)
                    row["result"] = self.verify(directory, row["plan"]["payload"], native_completed=True)
                    row.update(state="verified", verifiedAt=time.time())
                    durable_json(path, row)
                    return {**row["result"], "mutationReplayed": False}
                except Exception as error:
                    if row["state"] != "cancelled":
                        row["state"] = "failed"
                    row["error"] = {"code": getattr(error, "code", "write_failed"), "type": type(error).__name__}
                    durable_json(path, row)
                    if isinstance(error, CadenceError):
                        raise
                    raise CadenceError("write_failed", "Isolated artifact operation failed; no mutation replay is allowed.") from error
            finally:
                if event is not None:
                    with self.event_lock:
                        self.events.pop(plan_id, None)
                guard.close()

    def worker_error(self, directory, payload, process):
        return CadenceError("native_write_failed", "Native operation failed; retain its isolated output and receipt.", "worker")

    def cancel(self, plan_id, plan_digest):
        directory, path, row = self._load(plan_id)
        if row["digest"] != plan_digest:
            raise CadenceError("plan_digest_mismatch", "Plan digest does not match.")
        with self.event_lock:
            event = self.events.get(plan_id)
            if event is not None:
                event.set()
                return {"planId": plan_id, "cancelRequested": True, "state": "cancelling", "sourceModified": False}
        guard = self._guard()
        try:
            directory, path, row = self._load(plan_id)
            if row["state"] == "cancelled":
                return {"planId": plan_id, "state": "cancelled", "sourceModified": False}
            if row["state"] != "planned":
                raise CadenceError("too_late", "Only pending plans or this server's active owned process can be cancelled.")
            row["state"] = "cancelled"
            durable_json(path, row)
            return {"planId": plan_id, "state": "cancelled", "sourceModified": False}
        finally:
            guard.close()

    def recover(self, plan_id, plan_digest):
        guard = self._guard()
        try:
            directory, path, row = self._load(plan_id)
            if row["digest"] != plan_digest:
                raise CadenceError("plan_digest_mismatch", "Plan digest does not match.")
            if row["state"] in {"verified", "verified_recovered"}:
                return self._verified_result(directory, row)
            if row["state"] not in {"started", "failed"}:
                raise CadenceError("recovery_not_needed", "No started/failed artifact is available for verification.")
            pid = row.get("workerPid") or row.get("executorPid")
            if pid is None or process_status(pid) != "stopped":
                raise CadenceError("process_state_unknown", "Verification recovery requires proof the original worker is stopped.")
            result = self.verify(directory, row["plan"]["payload"], native_completed=False)
            row.update(state="verified_recovered", result=result, recoveredAt=time.time())
            durable_json(path, row)
            return {**result, "mutationReplayed": False}
        finally:
            guard.close()

    def jobs(self, offset=0, limit=100):
        if type(offset) is not int or not 0 <= offset <= 4096 or type(limit) is not int or not 1 <= limit <= 100:
            raise CadenceError("invalid_query", "Invalid isolated job page.")
        rows = []
        for directory in sorted(self.root.glob("plan-*")):
            if len(rows) >= 4096:
                raise CadenceError("result_limit", "Too many isolated jobs.")
            _, _, row = self._load(directory.name.removeprefix("plan-"))
            rows.append({"planId": row["plan"]["planId"], "planDigest": row["digest"], "state": row["state"],
                         "createdAt": row["plan"]["createdAt"], "kind": row["plan"]["kind"],
                         "error": row.get("error"), "canReplayMutation": False})
        return {"jobs": rows[offset:offset + limit], "total": len(rows),
                "nextOffset": offset + limit if offset + limit < len(rows) else None,
                "automaticReplay": False}
