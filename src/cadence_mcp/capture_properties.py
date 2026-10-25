"""Bounded effective-property reads using revision-bound part definition IDs."""
import json

from .core import CadenceError, checked_path, new_id
from .environment import run_tcl


def read_part_properties(capture, session_id: str, part_id: str) -> dict:
    with capture.lock:
        session = capture._session(session_id)
        part = next((row for row in session["data"]["part"] if row["objectId"] == part_id), None)
        if part is None:
            raise CadenceError("object_not_found", "Part ID does not belong to this immutable definition session.")
        schematic = next((row for row in session["data"]["schematic"] if row["objectId"] == part["schematicId"]), None)
        page = next((row for row in session["data"]["page"] if row["objectId"] == part["pageId"]), None)
        if schematic is None or page is None or page["schematicId"] != part["schematicId"]:
            raise CadenceError("invalid_worker_result", "Part definition contains inconsistent parents.", "decode")
        directory = checked_path(str(capture._workspace(session["workspaceId"])["directory"]),
                                 (capture.config.workspace_root,))
        output = directory / f"{new_id('part-properties')}.json"
        run_tcl(capture.config, "inspect_part_properties.tcl",
                [str(session["design"]), str(output), part_id, "100000", "512"], directory)
        capture._session(session_id)
        try:
            if not output.is_file() or output.stat().st_size > 1024 * 1024:
                raise ValueError("Missing or oversized property result")
            row = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(row, dict) or set(row) != {"partId", "schematicName", "pageName", "reference", "properties"}:
                raise ValueError("Invalid property result shape")
            if (row["partId"], row["schematicName"], row["pageName"], row["reference"]) != (
                part_id, schematic["name"], page["name"], part["reference"]
            ):
                raise ValueError("Property target identity mismatch")
            props = row["properties"]
            if not isinstance(props, list) or len(props) > 512:
                raise ValueError("Invalid property result count")
            names = set()
            for prop in props:
                if not isinstance(prop, dict) or set(prop) != {"name", "value"}:
                    raise ValueError("Invalid property fields")
                if any(not isinstance(value, str) for value in prop.values()) or not prop["name"] or prop["name"] in names:
                    raise ValueError("Invalid or duplicate property name")
                names.add(prop["name"])
        except (OSError, ValueError, TypeError) as error:
            raise CadenceError("invalid_worker_result", "Invalid part property inspection document.", "decode") from error
        output.unlink()  # Successful transient reads do not accumulate on disk.
        return {"partId": part_id, "revision": session["revision"], "generation": 1,
                "scope": "part_definition", "schematicName": row["schematicName"],
                "pageName": row["pageName"], "reference": row["reference"],
                "items": sorted(props, key=lambda prop: prop["name"]), "count": len(props),
                "readOnly": True, "notChecked": ["property_origin", "editability", "occurrence_properties"]}
