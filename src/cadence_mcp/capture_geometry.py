"""Native placement and actual transformed pin hotspots, never electrical inference."""
import json

from .core import CadenceError, checked_path, new_id
from .environment import run_tcl


def point(value):
    return isinstance(value, list) and len(value) == 2 and all(type(item) is int for item in value)


def read_part_geometry(capture, session_id, part_id):
    with capture.lock:
        session = capture._session(session_id)
        part = next((row for row in session["data"]["part"] if row["objectId"] == part_id), None)
        if part is None:
            raise CadenceError("object_not_found", "Part ID does not belong to this immutable definition session.")
        schematic = next((row for row in session["data"]["schematic"] if row["objectId"] == part["schematicId"]), None)
        page = next((row for row in session["data"]["page"] if row["objectId"] == part["pageId"]), None)
        if schematic is None or page is None or page["schematicId"] != part["schematicId"]:
            raise CadenceError("invalid_worker_result", "Part definition contains inconsistent parents.", "decode")
        expected_pins = {row["objectId"]: (row["number"], row["name"])
                         for row in session["data"]["pin"] if row["partId"] == part_id}
        directory = checked_path(str(capture._workspace(session["workspaceId"])["directory"]),
                                 (capture.config.workspace_root,))
        output = directory / f"{new_id('part-geometry')}.json"
        run_tcl(capture.config, "inspect_part_geometry.tcl",
                [str(session["design"]), str(output), part_id, "100000", "10000"], directory)
        capture._session(session_id)
        try:
            if not output.is_file() or output.stat().st_size > 4 * 1024 * 1024:
                raise ValueError("Missing or oversized geometry")
            row = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(row, dict) or set(row) != {"partId", "schematicName", "pageName", "reference", "location", "rotationCode", "mirrorCode", "pins"}:
                raise ValueError("Invalid geometry fields")
            if (row["partId"], row["schematicName"], row["pageName"], row["reference"]) != (part_id, schematic["name"], page["name"], part["reference"]):
                raise ValueError("Geometry target mismatch")
            if not point(row["location"]) or any(type(row[key]) is not int for key in ("rotationCode", "mirrorCode")):
                raise ValueError("Invalid placement values")
            if not isinstance(row["pins"], list) or len(row["pins"]) > 10000:
                raise ValueError("Invalid pin list")
            observed = {}
            for pin in row["pins"]:
                if not isinstance(pin, dict) or set(pin) != {"pinId", "number", "name", "hotSpot"}:
                    raise ValueError("Invalid pin fields")
                if any(not isinstance(pin[key], str) for key in ("pinId", "number", "name")) or not point(pin["hotSpot"]):
                    raise ValueError("Invalid pin values")
                if pin["pinId"] in observed:
                    raise ValueError("Duplicate pin")
                observed[pin["pinId"]] = (pin["number"], pin["name"])
            if observed != expected_pins:
                raise ValueError("Pin geometry does not match snapshot identities")
        except (OSError, ValueError, TypeError) as error:
            raise CadenceError("invalid_worker_result", "Invalid part geometry document.", "decode") from error
        output.unlink()
        return {**row, "revision": session["revision"], "generation": 1, "scope": "part_definition",
                "units": "capture_native_integer", "readOnly": True,
                "electricalConnectivityVerified": False,
                "notChecked": ["electrical_connectivity", "rendered_text_clearance", "occurrence_geometry"]}
