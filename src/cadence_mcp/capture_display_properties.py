"""Existing display-property layout edits; data/reference values remain intact."""
from datetime import datetime, timezone
import json

from .capture import CaptureService
from .capture_edit import CapturePropertyEdits, definition_baseline
from .capture_property_layers import read_property_layers
from .core import CadenceError, checked_path, sha256
from .environment import ADAPTERS
from .isolated_jobs import digest


class CaptureDisplayProperties(CapturePropertyEdits):
    kind = "capture_display_property"

    def plan(self, session_id, part_id, property_name, location, rotation, display_type):
        if not isinstance(property_name, str) or not 1 <= len(property_name) <= 128 or "\x00" in property_name:
            raise CadenceError("invalid_property_name", "Provide an exact existing display-property name.")
        if location is not None and (not isinstance(location, list) or len(location) != 2 or any(type(v) is not int or not -1000000 <= v <= 1000000 for v in location)):
            raise CadenceError("invalid_display_change", "Location requires two bounded owner-local integer coordinates.")
        if rotation is not None and (type(rotation) is not int or not 0 <= rotation <= 3):
            raise CadenceError("invalid_display_change", "Rotation code must be 0 through 3.")
        if display_type is not None and (type(display_type) is not int or not 0 <= display_type <= 4):
            raise CadenceError("invalid_display_change", "Display type code must be 0 through 4.")
        if location is None and rotation is None and display_type is None:
            raise CadenceError("invalid_display_change", "Provide at least one explicit layout change.")
        with self.capture.lock:
            session = self.capture._session(session_id)
            part = next((row for row in session["data"]["part"] if row["objectId"] == part_id), None)
            if part is None:
                raise CadenceError("object_not_found", "Part does not belong to this immutable session.")
            if sum(row["pageId"] == part["pageId"] and row["reference"] == part["reference"] for row in session["data"]["part"]) != 1:
                raise CadenceError("ambiguous_target", "Shared-reference display editing requires a unit-aware operation.")
            layers = read_property_layers(self.capture, session_id, part_id)
            candidates = [row for row in layers["display"] if row["name"] == property_name]
            if len(candidates) != 1:
                raise CadenceError("display_property_not_found", "Existing display property is missing or ambiguous; use its exact name.")
            old = candidates[0]
            expected = {**old, "location": old["location"] if location is None else location,
                        "rotationCode": old["rotationCode"] if rotation is None else rotation,
                        "displayTypeCode": old["displayTypeCode"] if display_type is None else display_type}
            self.capture._session(session_id)
            payload = {"sourceDesign": str(session["design"]), "sourceFingerprint": session["revision"],
                       "partId": part_id, "schematicName": layers["schematicName"], "pageName": layers["pageName"],
                       "reference": layers["reference"], "property": property_name, "oldDisplay": old, "expectedDisplay": expected,
                       "dataPropertiesDigest": digest({"user": layers["user"], "effective": layers["effective"]}),
                       "otherDisplayDigest": digest([row for row in layers["display"] if row["name"] != property_name]),
                       "definitionBaselineDigest": definition_baseline(session["data"])}
        return self.create_plan(payload)

    def preview(self, payload):
        return {key: payload[key] for key in ("partId", "schematicName", "pageName", "reference", "property", "oldDisplay", "expectedDisplay", "sourceFingerprint")}

    def preflight(self, payload):
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower() != ".dsn" or sha256(source) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "Source workspace changed after display-property planning.")

    def native_command(self, directory, payload):
        old, new = payload["oldDisplay"], payload["expectedDisplay"]
        return [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "edit_display_property.tcl",
                self.config.install_root, directory / "design.dsn", directory / "native-result.json", payload["partId"], "100000",
                payload["property"], *map(str, old["location"]), str(old["rotationCode"]), str(old["displayTypeCode"]),
                *map(str, new["location"]), str(new["rotationCode"]), str(new["displayTypeCode"]),
                payload["schematicName"], payload["pageName"], payload["reference"]]

    def verify(self, directory, payload, native_completed):
        target = checked_path(str(directory / "design.dsn"), (directory,))
        if target.stat().st_size > 128 * 1024 * 1024:
            raise CadenceError("output_limit", "Output design exceeds the size limit.")
        before = sha256(target)
        if native_completed:
            receipt = checked_path(str(directory / "native-result.json"), (directory,))
            if receipt.stat().st_size > 16384:
                raise CadenceError("invalid_worker_result", "Invalid native display-property receipt.")
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data != {"saved": True, "partId": payload["partId"], "property": payload["property"], "operation": "display_layout"}:
                raise CadenceError("invalid_worker_result", "Native display-property receipt mismatch.")
        verifier = CaptureService(self.config)
        verifier.workspaces["isolated"] = {"directory": directory, "manifest": {"copiedFingerprint": before}}
        session = verifier.open("isolated")
        sid = session["sessionId"]
        try:
            objects = verifier.sessions[sid]["data"]
            if definition_baseline(objects) != payload["definitionBaselineDigest"]:
                raise CadenceError("unexpected_connectivity_change", "Display layout edit changed definitions or pin nets.", "verify")
            schematics = {row["objectId"]: row["name"] for row in objects["schematic"]}
            pages = {row["objectId"]: row["name"] for row in objects["page"]}
            candidates = [row for row in objects["part"] if schematics[row["schematicId"]] == payload["schematicName"]
                          and pages[row["pageId"]] == payload["pageName"] and row["reference"] == payload["reference"]]
            if len(candidates) != 1:
                raise CadenceError("ambiguous_target", "Saved display-property target is missing or ambiguous.")
            layers = read_property_layers(verifier, sid, candidates[0]["objectId"])
            actual = next((row for row in layers["display"] if row["name"] == payload["property"]), None)
            if actual != payload["expectedDisplay"]:
                raise CadenceError("display_verification_failed", "Saved display-property layout/value does not match the explicit plan.", "verify")
            if digest({"user": layers["user"], "effective": layers["effective"]}) != payload["dataPropertiesDigest"]:
                raise CadenceError("unexpected_property_change", "Display edit altered a user/effective data property.", "verify")
            if digest([row for row in layers["display"] if row["name"] != payload["property"]]) != payload["otherDisplayDigest"]:
                raise CadenceError("unexpected_property_change", "An unrelated display property changed.", "verify")
        finally:
            verifier.close(sid)
        if sha256(target) != before:
            raise CadenceError("target_changed", "Output changed during independent verification.")
        plan_id = directory.name.removeprefix("plan-")
        artifact = {"artifactId": f"display-property-{plan_id}", "kind": "capture_edited_design", "workspaceRelativePath": "design.dsn",
                    "sha256": before, "size": target.stat().st_size, "producedByJob": plan_id,
                    "sourceFingerprint": payload["sourceFingerprint"], "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "validated"}
        return {"planId": plan_id, "state": "verified" if native_completed else "verified_recovered", "property": payload["property"],
                "observedDisplay": actual, "sourceModified": False,
                "outputWorkspaceRelativePath": directory.relative_to(self.config.workspace_root).as_posix(),
                "nativeCompletionVerified": native_completed, "independentReopenVerified": True,
                "definitionBaselinePreserved": True, "dataPropertiesPreserved": True, "otherDisplayPropertiesPreserved": True,
                "designPassed": None, "artifact": artifact,
                "notChecked": ["font_descriptor", "rendered_text_bounds", "occurrence_connectivity", "native_drc"]}
