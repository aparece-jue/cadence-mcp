"""Isolated display-property edits that preserve the underlying data values."""
from datetime import datetime, timezone
import json

from .capture import CaptureService
from .capture_cache_replace import read_state, unit_graph
from .capture_display_fonts import read_fonts
from .capture_references import read_units
from .capture_wire import connection_digest, inventory
from .capture_edit import CapturePropertyEdits, definition_baseline
from .capture_property_layers import read_property_layers
from .core import CadenceError, checked_path, sha256
from .environment import ADAPTERS
from .isolated_jobs import digest


# Fixed descriptor verified in SPB 24.1. Font editing is a separate task.
FOOTPRINT_DISPLAY_FONT = ["Arial", -11, 0, 0, 0, 400, 0, 0, 0, 0, 7, 0, 1, 16]


class CaptureDisplayProperties(CapturePropertyEdits):
    kind = "capture_display_property"

    def plan(self, session_id, part_id, property_name, location, rotation, display_type, operation="layout"):
        if operation not in ("layout", "create", "delete"):
            raise CadenceError("invalid_display_change", "Choose layout, create or delete.")
        if operation != "layout" and property_name != "PCB Footprint":
            raise CadenceError("unsupported_display_lifecycle", "Create and delete support only PCB Footprint displays.")
        fields = (location, rotation, display_type)
        if operation == "create" and any(value is None for value in fields):
            raise CadenceError("invalid_display_change", "Creation requires location, rotation and display type.")
        if operation == "delete" and any(value is not None for value in fields):
            raise CadenceError("invalid_display_change", "Deletion takes no layout fields.")
        if not isinstance(property_name, str) or not 1 <= len(property_name) <= 128 or "\x00" in property_name:
            raise CadenceError("invalid_property_name", "Provide an exact existing display-property name.")
        if location is not None and (not isinstance(location, list) or len(location) != 2 or any(type(v) is not int or not -1000000 <= v <= 1000000 for v in location)):
            raise CadenceError("invalid_display_change", "Location requires two bounded owner-local integer coordinates.")
        if rotation is not None and (type(rotation) is not int or not 0 <= rotation <= 3):
            raise CadenceError("invalid_display_change", "Rotation code must be 0 through 3.")
        if display_type is not None and (type(display_type) is not int or not 0 <= display_type <= 4):
            raise CadenceError("invalid_display_change", "Display type code must be 0 through 4.")
        if operation == "layout" and all(value is None for value in fields):
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
            if operation == "create":
                if candidates:
                    raise CadenceError("display_property_exists", "The display property already exists.")
                value = next((row["value"] for row in layers["effective"] if row["name"] == property_name), None)
                if not value:
                    raise CadenceError("property_unavailable", "Creation requires an existing nonempty PCB Footprint value.")
                old = None
                expected = {"name": property_name, "value": value, "location": location,
                            "rotationCode": rotation, "displayTypeCode": display_type, "colorCode": 0}
            else:
                if len(candidates) != 1:
                    raise CadenceError("display_property_not_found", "Existing display property is missing or ambiguous; use its exact name.")
                old = candidates[0]
                expected = None if operation == "delete" else {
                    **old, "location": old["location"] if location is None else location,
                    "rotationCode": old["rotationCode"] if rotation is None else rotation,
                    "displayTypeCode": old["displayTypeCode"] if display_type is None else display_type,
                }
            payload = {"sourceDesign": str(session["design"]), "sourceFingerprint": session["revision"],
                       "partId": part_id, "schematicName": layers["schematicName"], "pageName": layers["pageName"],
                       "reference": layers["reference"], "property": property_name, "oldDisplay": old, "expectedDisplay": expected,
                       "dataPropertiesDigest": digest({"user": layers["user"], "effective": layers["effective"]}),
                       "otherDisplayDigest": digest([row for row in layers["display"] if row["name"] != property_name]),
                       "definitionBaselineDigest": definition_baseline(session["data"])}
            if operation != "layout":
                payload.update(self.lifecycle_baseline(session_id, session, payload, operation))
            self.capture._session(session_id)
        return self.create_plan(payload)

    def lifecycle_baseline(self, session_id, session, payload, operation):
        units = read_units(self.capture, session_id)
        unit = units[payload["partId"]]
        if unit["kind"] != "placed" or unit["isExternalDesignPart"]:
            raise CadenceError("unsupported_display_lifecycle", "A local placed instance is required.")
        native_id = unit["nativeId"]
        design = session["design"]
        state = read_state(self.config, design, design.parent, units)
        target = next(row for row in state if row["nativeId"] == native_id)
        name = payload["property"]
        old = next((row for row in target["display"] if row["name"] == name), None)
        if old != payload["oldDisplay"]:
            raise CadenceError("display_precondition_changed", "The two native display snapshots disagree.")
        target["display"] = [row for row in target["display"] if row["name"] != name]
        fonts = read_fonts(self.config, design, design.parent, units)
        target_fonts = next(row["fonts"] for row in fonts if row["nativeId"] == native_id)
        if any(row["name"] == name for row in target_fonts) != (old is not None):
            raise CadenceError("display_precondition_changed", "Display and font snapshots disagree.")
        target_fonts[:] = [row for row in target_fonts if row["name"] != name]
        if operation == "create":
            target["display"].append(payload["expectedDisplay"])
            target["display"].sort(key=lambda row: row["name"])
            target_fonts.append({"name": name, "font": FOOTPRINT_DISPLAY_FONT, "fontDefault": 0, "defaultFontType": 10})
            target_fonts.sort(key=lambda row: row["name"])
        return {"operation": operation, "nativeId": native_id, "expectedStateDigest": digest(state),
                "expectedFontDigest": digest(fonts), "unitDigest": digest(unit_graph(units)),
                "connectionDigest": connection_digest(session["data"], inventory(self.capture, session_id))}

    def preview(self, payload):
        keys = ("partId", "schematicName", "pageName", "reference", "property", "oldDisplay", "expectedDisplay", "sourceFingerprint")
        if "operation" in payload:
            keys += ("operation", "nativeId")
        return {key: payload[key] for key in keys}

    def preflight(self, payload):
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower() != ".dsn" or sha256(source) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "Source workspace changed after display-property planning.")

    def native_command(self, directory, payload):
        old, new = payload["oldDisplay"], payload["expectedDisplay"]
        operation = payload.get("operation")
        # Absent sides are ignored by the native worker. Keep legacy argv and receipts unchanged.
        old, new = old or new, new or old
        command = [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "edit_display_property.tcl",
                self.config.install_root, directory / "design.dsn", directory / "native-result.json", payload["partId"], "100000",
                payload["property"], *map(str, old["location"]), str(old["rotationCode"]), str(old["displayTypeCode"]),
                *map(str, new["location"]), str(new["rotationCode"]), str(new["displayTypeCode"]),
                payload["schematicName"], payload["pageName"], payload["reference"]]
        if operation:
            command.extend((operation, str(payload["nativeId"])))
        return command

    def verify(self, directory, payload, native_completed):
        target = checked_path(str(directory / "design.dsn"), (directory,))
        if target.stat().st_size > 128 * 1024 * 1024:
            raise CadenceError("output_limit", "Output design exceeds the size limit.")
        before = sha256(target)
        operation = payload.get("operation")
        if operation:
            self.preflight(payload)
        if native_completed:
            receipt = checked_path(str(directory / "native-result.json"), (directory,))
            if receipt.stat().st_size > 16384:
                raise CadenceError("invalid_worker_result", "Invalid native display-property receipt.")
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data != {"saved": True, "partId": payload["partId"], "property": payload["property"], "operation": f"display_{operation or 'layout'}"}:
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
            if operation:
                units = read_units(verifier, sid)
                if units[candidates[0]["objectId"]]["nativeId"] != payload["nativeId"] or digest(unit_graph(units)) != payload["unitDigest"]:
                    raise CadenceError("display_identity_changed", "The saved native instance graph differs.", "verify")
                if connection_digest(objects, inventory(verifier, sid)) != payload["connectionDigest"]:
                    raise CadenceError("unexpected_connectivity_change", "Display edit changed connection objects.", "verify")
                if digest(read_state(self.config, target, directory, units)) != payload["expectedStateDigest"]:
                    raise CadenceError("unexpected_property_change", "Saved instance properties or geometry differ from the plan.", "verify")
                if digest(read_fonts(self.config, target, directory, units)) != payload["expectedFontDigest"]:
                    raise CadenceError("display_font_persistence_mismatch", "Saved display fonts differ from the plan.", "verify")
            if actual != payload["expectedDisplay"]:
                raise CadenceError("display_verification_failed", "Saved display-property layout/value does not match the explicit plan.", "verify")
            if digest({"user": layers["user"], "effective": layers["effective"]}) != payload["dataPropertiesDigest"]:
                raise CadenceError("unexpected_property_change", "Display edit altered a user/effective data property.", "verify")
            if digest([row for row in layers["display"] if row["name"] != payload["property"]]) != payload["otherDisplayDigest"]:
                raise CadenceError("unexpected_property_change", "An unrelated display property changed.", "verify")
        finally:
            verifier.close(sid)
        if operation:
            self.preflight(payload)
        if sha256(target) != before:
            raise CadenceError("target_changed", "Output changed during independent verification.")
        plan_id = directory.name.removeprefix("plan-")
        artifact = {"artifactId": f"display-property-{plan_id}", "kind": "capture_edited_design", "workspaceRelativePath": "design.dsn",
                    "sha256": before, "size": target.stat().st_size, "producedByJob": plan_id,
                    "sourceFingerprint": payload["sourceFingerprint"], "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "validated"}
        coverage = {"operation": operation, "modeledAllInstanceStateVerified": True, "allDisplayFontsVerified": True} if operation else {}
        not_checked = ["rendered_text_bounds", "occurrence_connectivity", "native_drc"]
        if not operation:
            not_checked.insert(0, "font_descriptor")
        return {**coverage, "planId": plan_id, "state": "verified" if native_completed else "verified_recovered", "property": payload["property"],
                "observedDisplay": actual, "sourceModified": False,
                "outputWorkspaceRelativePath": directory.relative_to(self.config.workspace_root).as_posix(),
                "nativeCompletionVerified": native_completed, "independentReopenVerified": True,
                "definitionBaselinePreserved": True, "dataPropertiesPreserved": True, "otherDisplayPropertiesPreserved": True,
                "designPassed": None, "artifact": artifact,
                "notChecked": not_checked}
