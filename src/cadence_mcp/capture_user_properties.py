"""Explicit user-property lifecycle on new isolated DSN copies.

Native identity/source/model fields are handled by dedicated operations instead.
Deletion asserts an explicit expected effective fallback, including absence.
"""
from datetime import datetime, timezone
import json
import re

from .capture import CaptureService
from .capture_edit import CapturePropertyEdits, definition_baseline
from .capture_property_layers import read_property_layers
from .core import CadenceError, checked_path, sha256
from .environment import ADAPTERS
from .isolated_jobs import digest


PROTECTED = {"value", "pcbfootprint", "reference", "partreference", "designator", "name", "primitive",
             "implementation", "implementationpath", "implementationtype", "sourcelibrary", "sourcepackage", "sourcepart",
             "locationxcoordinate", "locationycoordinate", "rotation", "mirror", "powerpinsvisible", "pspicetemplate"}
METADATA = {"manufacturer", "mpn", "tolerance", "voltagerating", "powerrating", "datasheet", "description"}


def check_name(name):
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or name.strip() != name or re.search(r"[\x00-\x1f\x7f]", name):
        raise CadenceError("invalid_property_name", "A bounded non-control user-property name is required.")
    normalized = "".join(char for char in name.casefold() if char.isalnum())
    if normalized in PROTECTED or normalized.startswith(("implementation", "source", "pspice", "net", "pin")):
        raise CadenceError("protected_property", "Identity, source, model and connectivity fields require dedicated operations.")
    return normalized


def other_users(props, name):
    return digest(sorted((row["name"], row["value"]) for row in props if row["name"] != name))


class CaptureUserProperties(CapturePropertyEdits):
    kind = "capture_user_property"

    def plan(self, session_id, part_id, operation, property_name, value, expected_after_delete):
        normalized = check_name(property_name)
        if operation not in {"set", "delete"}:
            raise CadenceError("invalid_property_change", "Operation must be set or delete.")
        for content in (value, expected_after_delete):
            if content is not None and (not isinstance(content, str) or len(content) > 1024 or "\x00" in content):
                raise CadenceError("invalid_property_change", "Property expectations must be bounded strings or null.")
        if (operation == "set" and (value is None or expected_after_delete is not None)) or (operation == "delete" and value is not None):
            raise CadenceError("invalid_property_change", "Set requires value; delete requires null value and an explicit fallback expectation (null means absent).")
        with self.capture.lock:
            session = self.capture._session(session_id)
            part = next((row for row in session["data"]["part"] if row["objectId"] == part_id), None)
            if part is None:
                raise CadenceError("object_not_found", "Part does not belong to this immutable session.")
            if sum(row["pageId"] == part["pageId"] and row["reference"] == part["reference"] for row in session["data"]["part"]) != 1:
                raise CadenceError("ambiguous_target", "Shared references/multi-unit property editing requires the dedicated unit-aware operation.")
            layers = read_property_layers(self.capture, session_id, part_id)
            effective = {row["name"]: row["value"] for row in layers["effective"]}
            user = {row["name"]: row["value"] for row in layers["user"]}
            names = set(effective) | set(user) | {row["name"] for row in layers["display"]}
            if any(name.casefold() == property_name.casefold() and name != property_name for name in names):
                raise CadenceError("property_name_case_conflict", "An existing property has a different spelling/case; use its exact name.")
            if property_name in effective and property_name not in user and normalized not in METADATA and not property_name.startswith(("MCP_", "USER_")):
                raise CadenceError("effective_attribute_not_user_property", "An inherited/built-in effective field is not an approved user metadata override.")
            if operation == "delete" and property_name not in user:
                raise CadenceError("user_property_not_found", "Delete removes an existing explicit user property only.")
            old = user.get(property_name)
            if old is not None and (len(old) > 4096 or "\x00" in old):
                raise CadenceError("input_limit", "Existing user-property value exceeds supported argument bounds.")
            self.capture._session(session_id)
            payload = {"sourceDesign": str(session["design"]), "sourceFingerprint": session["revision"],
                       "partId": part_id, "schematicName": layers["schematicName"], "pageName": layers["pageName"],
                       "reference": layers["reference"], "operation": operation, "property": property_name,
                       "oldUserExists": property_name in user, "oldUserValue": old, "oldEffectiveValue": effective.get(property_name),
                       "value": value, "expectedEffectiveAfter": value if operation == "set" else expected_after_delete,
                       "otherUserPropertiesDigest": other_users(layers["user"], property_name),
                       "definitionBaselineDigest": definition_baseline(session["data"])}
        return self.create_plan(payload)

    def preview(self, payload):
        return {key: payload[key] for key in ("partId", "schematicName", "pageName", "reference", "operation", "property",
                    "oldUserExists", "oldUserValue", "oldEffectiveValue", "value", "expectedEffectiveAfter", "sourceFingerprint")}

    def preflight(self, payload):
        check_name(payload["property"])
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower() != ".dsn" or sha256(source) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "Source workspace changed after user-property planning.")

    def native_command(self, directory, payload):
        return [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "edit_user_property.tcl",
                self.config.install_root, directory / "design.dsn", directory / "native-result.json", payload["partId"], "100000",
                payload["property"], payload["operation"], "1" if payload["oldUserExists"] else "0",
                payload["oldUserValue"] or "", payload["value"] or "", payload["schematicName"], payload["pageName"], payload["reference"]]

    def verify(self, directory, payload, native_completed):
        target = checked_path(str(directory / "design.dsn"), (directory,))
        if target.stat().st_size > 128 * 1024 * 1024:
            raise CadenceError("output_limit", "Output design exceeds the size limit.")
        before = sha256(target)
        if native_completed:
            receipt = checked_path(str(directory / "native-result.json"), (directory,))
            if receipt.stat().st_size > 16384:
                raise CadenceError("invalid_worker_result", "Invalid native user-property receipt.")
            native = json.loads(receipt.read_text(encoding="utf-8"))
            if native != {"saved": True, "partId": payload["partId"], "property": payload["property"], "operation": payload["operation"]}:
                raise CadenceError("invalid_worker_result", "Native user-property receipt mismatch.")
        verifier = CaptureService(self.config)
        verifier.workspaces["isolated"] = {"directory": directory, "manifest": {"copiedFingerprint": before}}
        opened = verifier.open("isolated")
        sid = opened["sessionId"]
        try:
            data = verifier.sessions[sid]["data"]
            if definition_baseline(data) != payload["definitionBaselineDigest"]:
                raise CadenceError("unexpected_connectivity_change", "User-property edit changed definition structure or pin nets.", "verify")
            schematics = {row["objectId"]: row["name"] for row in data["schematic"]}
            pages = {row["objectId"]: row["name"] for row in data["page"]}
            candidates = [row for row in data["part"] if schematics[row["schematicId"]] == payload["schematicName"]
                          and pages[row["pageId"]] == payload["pageName"] and row["reference"] == payload["reference"]]
            if len(candidates) != 1:
                raise CadenceError("ambiguous_target", "Saved user-property target is missing or ambiguous.")
            layers = read_property_layers(verifier, sid, candidates[0]["objectId"])
            effective = {row["name"]: row["value"] for row in layers["effective"]}
            user = {row["name"]: row["value"] for row in layers["user"]}
            expected_exists = payload["operation"] == "set"
            if (payload["property"] in user) != expected_exists or (expected_exists and user[payload["property"]] != payload["value"]):
                raise CadenceError("user_property_verification_failed", "Explicit user property does not match the plan.", "verify")
            actual = effective.get(payload["property"])
            if actual != payload["expectedEffectiveAfter"]:
                raise CadenceError("effective_fallback_mismatch", "Effective result does not match the explicit post-edit/fallback expectation.", "verify")
            if other_users(layers["user"], payload["property"]) != payload["otherUserPropertiesDigest"]:
                raise CadenceError("unexpected_property_change", "An unrelated explicit user property changed.", "verify")
        finally:
            verifier.close(sid)
        if sha256(target) != before:
            raise CadenceError("target_changed", "Output changed during independent user-property verification.")
        plan_id = directory.name.removeprefix("plan-")
        artifact = {"artifactId": f"user-property-{plan_id}", "kind": "capture_edited_design", "workspaceRelativePath": "design.dsn",
                    "sha256": before, "size": target.stat().st_size, "producedByJob": plan_id,
                    "sourceFingerprint": payload["sourceFingerprint"], "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "validated"}
        return {"planId": plan_id, "state": "verified" if native_completed else "verified_recovered", "operation": payload["operation"],
                "property": payload["property"], "userPropertyExists": expected_exists, "observedEffectiveValue": actual,
                "expectedEffectiveValue": payload["expectedEffectiveAfter"], "sourceModified": False,
                "outputWorkspaceRelativePath": directory.relative_to(self.config.workspace_root).as_posix(),
                "nativeCompletionVerified": native_completed, "independentReopenVerified": True,
                "definitionBaselinePreserved": True, "unrelatedUserPropertiesPreserved": True,
                "electricalBehaviorVerified": False, "designPassed": None, "artifact": artifact,
                "notChecked": ["occurrence_connectivity", "native_drc", "electrical_behavior", "display_property_editing", "full_inheritance_chain"]}
