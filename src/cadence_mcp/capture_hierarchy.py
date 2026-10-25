"""Occurrence structure: preserves repeated instance paths, no connectivity claim."""
import json

from .core import CadenceError, checked_path, new_id
from .environment import run_tcl


def validate_hierarchy(rows):
    try:
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
            raise ValueError("Invalid occurrence count")
        by_id, siblings, property_count, text_bytes = {}, set(), 0, 0
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"occurrenceId", "parentId", "depth", "path", "hierarchicalPath", "reference", "properties"}:
                raise ValueError("Invalid occurrence shape")
            if any(not isinstance(row[key], str) for key in ("occurrenceId", "path", "hierarchicalPath", "reference")):
                raise ValueError("Invalid occurrence values")
            for key, limit in (("occurrenceId", 256), ("path", 16384), ("hierarchicalPath", 16384), ("reference", 256)):
                if len(row[key]) > limit:
                    raise ValueError("Occurrence identity text exceeds limit")
                # Generated occurrence IDs are not part of the native text budget.
                if key != "occurrenceId":
                    text_bytes += len(row[key].encode("utf-8"))
            if not row["occurrenceId"] or row["occurrenceId"] in by_id:
                raise ValueError("Duplicate occurrence identity")
            if type(row["depth"]) is not int or not 0 <= row["depth"] <= 64:
                raise ValueError("Invalid depth")
            if not by_id:
                if row["parentId"] is not None or row["depth"] != 0:
                    raise ValueError("Invalid root")
            elif not isinstance(row["parentId"], str) or row["parentId"] not in by_id or row["depth"] != by_id[row["parentId"]]["depth"] + 1:
                raise ValueError("Invalid parent or cycle")
            # Native raw paths collapse physical packages (U3A/U3B share U3).
            # Full reference plus parent context identifies a unit in this snapshot.
            if by_id:
                identity = (row["parentId"], row["reference"])
                if not row["reference"] or identity in siblings:
                    raise ValueError("Duplicate/empty sibling unit reference")
                siblings.add(identity)
            properties = row["properties"]
            if not isinstance(properties, list) or len(properties) > 512:
                raise ValueError("Invalid occurrence properties")
            names = set()
            for prop in properties:
                if not isinstance(prop, dict) or set(prop) != {"name", "value"} or any(not isinstance(v, str) for v in prop.values()):
                    raise ValueError("Invalid property values")
                if not 1 <= len(prop["name"]) <= 256 or len(prop["value"]) > 16384 or prop["name"] in names:
                    raise ValueError("Duplicate/empty property name")
                names.add(prop["name"])
                text_bytes += len(prop["name"].encode("utf-8")) + len(prop["value"].encode("utf-8"))
            property_count += len(properties)
            if property_count > 100000:
                raise ValueError("Too many occurrence properties")
            if text_bytes > 8 * 1024 * 1024:
                raise ValueError("Hierarchy text exceeds budget")
            by_id[row["occurrenceId"]] = row

    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise CadenceError("invalid_worker_result", "Invalid occurrence hierarchy document.", "decode") from error


def get_hierarchy(capture, session_id, cursor, limit):
    with capture.lock:
        session = capture._session(session_id)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise CadenceError("invalid_query", "Invalid hierarchy page size.")
        if "hierarchy" not in session:
            directory = checked_path(str(capture._workspace(session["workspaceId"])["directory"]),
                                     (capture.config.workspace_root,))
            output = directory / f"{new_id('hierarchy')}.json"
            run_tcl(capture.config, "inspect_hierarchy.tcl", [str(session["design"]), str(output)], directory)
            capture._session(session_id)
            try:
                if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Invalid hierarchy output size")
                rows = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise CadenceError("invalid_worker_result", "Invalid hierarchy inspection output.", "decode") from error
            validate_hierarchy(rows)
            output.unlink()
            segments = {}
            normalized = []
            for row in rows:
                parent = row["parentId"]
                path = [] if parent is None else segments[parent] + [row["reference"]]
                segments[row["occurrenceId"]] = path
                normalized.append({**row, "instancePathSegments": path})
            session["hierarchy"], session["hierarchyCursors"] = normalized, {}
        offset = 0
        if cursor is not None:
            saved = session["hierarchyCursors"].get(cursor)
            if saved is None or saved[0] != limit:
                raise CadenceError("stale_cursor", "Hierarchy cursor is bound to its session and page size.")
            offset = saved[1]
        rows = session["hierarchy"]
        items = rows[offset:offset + limit]
        next_cursor = None
        if offset + limit < len(rows):
            if len(session["hierarchyCursors"]) >= 10000:
                raise CadenceError("cursor_limit", "Too many hierarchy cursors; open a fresh session.")
            next_cursor = new_id("hierarchy-cursor")
            session["hierarchyCursors"][next_cursor] = (limit, offset + limit)
        return {"sessionId": session_id, "revision": session["revision"], "items": items,
                "total": len(rows), "nextCursor": next_cursor, "complete": next_cursor is None,
                "scope": "occurrence_structure", "occurrenceConnectivityVerified": False,
                "identityScope": "session_revision",
                "rawPathsUnique": False,
                "notChecked": ["occurrence_pin_net_connectivity", "root_component_properties", "external_design_closure"]}
