"""Retire a verified owned DSN while retaining its immutable provenance."""
import json
import re
import stat
import time

from .core import CadenceError, checked_path, sha256
from .gui_jobs import acquire_guard, durable_json
from .owned_design import VERIFIED_STATES, journal_source_matches


PENDING = "artifact_deletion_pending"
DELETED = "artifact_deleted"


def _present(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _assert_no_dependents(root, target, producer_record):
    now = time.time()
    for index, record in enumerate(root.glob("*/plan-*/plan.json")):
        if index >= 65536:
            raise CadenceError("dependency_check_failed", "Too many isolated plans to verify deletion safety.")
        if record == producer_record:
            continue
        try:
            if checked_path(str(record), (root,)) != record or record.stat().st_size > 512 * 1024:
                raise ValueError("Unsafe downstream journal")
            row = json.loads(record.read_text(encoding="utf-8"))
            if not journal_source_matches(row["plan"]["payload"], target):
                continue
            if row["state"] in VERIFIED_STATES | {"cancelled", PENDING, DELETED}:
                continue
            if row["state"] == "planned" and now > row["plan"]["expiresAt"]:
                continue
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise CadenceError("dependency_check_failed", "Cannot verify isolated downstream plans.") from error
        raise CadenceError("artifact_in_use", "A pending or recoverable downstream job still uses the DSN.")


def delete_owned_design(producer, plan_id, plan_digest, expected_sha256):
    """Delete only the producer's exact output and durably retain the receipt."""
    capture = producer.capture
    with capture.lock, producer._guard():
        directory, record, row = producer._load(plan_id)
        if row["digest"] != plan_digest:
            raise CadenceError("plan_digest_mismatch", "Plan digest does not match.")
        state = row["state"]
        if state not in VERIFIED_STATES | {PENDING, DELETED}:
            raise CadenceError("output_unverified", "Only a verified owned DSN can be deleted.")
        artifact = row["result"]["artifact"]
        if artifact["sha256"] != expected_sha256:
            raise CadenceError("target_changed", "The expected fingerprint does not match the verified DSN.")
        relative = artifact["workspaceRelativePath"]
        expected_name = (producer.design_relative_path(row["plan"]["payload"])
                         if producer.kind == "capture_design_save_as" else "design.dsn")
        if (relative != expected_name or artifact["producedByJob"] != plan_id
                or directory != producer.root / f"plan-{plan_id}" or record != directory / "plan.json"
                or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256)):
            raise CadenceError("invalid_plan", "Verified DSN provenance does not match its owned path.")
        target = directory / relative
        identity = {"planId": plan_id, "planDigest": plan_digest, "artifactId": artifact["artifactId"],
                    "sha256": expected_sha256, "workspaceRelativePath": relative}
        if state in {PENDING, DELETED}:
            receipt = row.get("deletion")
            if not isinstance(receipt, dict) or any(receipt.get(key) != value for key, value in identity.items()):
                raise CadenceError("invalid_plan", "The deletion receipt does not match the verified DSN.")
        with acquire_guard(directory):
            present = _present(target)
            if state == DELETED:
                if present:
                    raise CadenceError("target_changed", "A path already retired by this plan has reappeared.")
                return {**row["deletion"], "state": DELETED, "mutationReplayed": False}

            if present:
                if any(session["design"] == target for session in capture.sessions.values()):
                    raise CadenceError("artifact_in_use", "Close active Capture sessions before deleting this DSN.")
                if any(_present(lock) for lock in (target.with_suffix(".dsnlck"), target.with_suffix(".dsn.lck"))):
                    raise CadenceError("artifact_in_use", "A native Capture lock protects this DSN.")
                _assert_no_dependents(producer.root.parent, target, record)
                info = target.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or checked_path(str(target), (directory,)) != target
                        or sha256(target) != expected_sha256):
                    raise CadenceError("target_changed", "The DSN no longer matches the verified owned output.")
            elif state != PENDING:
                raise CadenceError("target_changed", "The verified DSN disappeared before deletion was recorded.")

            if state != PENDING:
                row["deletion"] = {**identity, "requestedAt": time.time()}
                row["state"] = PENDING
                durable_json(record, row)
            if present:
                try:
                    target.unlink()
                except PermissionError as error:
                    if state != PENDING:
                        row["state"] = state
                        del row["deletion"]
                        durable_json(record, row)
                    raise CadenceError("artifact_in_use", "The DSN could not be removed while another process may hold it.") from error
            if _present(target):
                raise CadenceError("target_changed", "The DSN path is still present after removal.")
            row["state"] = DELETED
            row["deletion"]["deletedAt"] = time.time()
            durable_json(record, row)
            return {**row["deletion"], "state": DELETED, "mutationReplayed": False}
