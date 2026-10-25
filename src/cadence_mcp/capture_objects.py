"""Separate bounded connection/graphic inventories of immutable DSN definitions."""
from collections import Counter
import json

from .capture_geometry import point
from .core import CadenceError, checked_path, new_id
from .environment import run_tcl

MODES = {"connections": {"wire", "alias", "global", "port", "offpage", "nc"},
         "graphics": {"part_bounds", "display_property", "graphic", "titleblock"}}
BASE_GRAPHIC = {"name": str, "location": "point", "rotationCode": int, "mirrorCode": int, "bounds": "rect"}
SYMBOL = {"name": str, "sourceSymbol": str, "location": "point", "hotSpot": "point",
          "rotationCode": int, "mirrorCode": int, "isBus": bool}
ATTRIBUTES = {
    "wire": {"net": str, "points": "points"},
    "alias": {"wireId": str, "name": str, "location": "point"},
    "global": SYMBOL, "port": SYMBOL, "offpage": SYMBOL,
    "nc": {"partId": str, "pinId": str, "reference": str, "number": str, "hotSpot": "point"},
    "part_bounds": {**BASE_GRAPHIC, "partId": str, "reference": str},
    "display_property": {"partId": str, "name": str, "value": str, "location": "point", "rotationCode": int,
                         "displayTypeCode": int, "colorCode": int, "bounds": "rect", "boundsDirty": bool},
    "graphic": {**BASE_GRAPHIC, "text": "nullable_text"},
    "titleblock": {**BASE_GRAPHIC, "text": "nullable_text", "properties": "properties"},
}


def value_valid(value, rule):
    if isinstance(rule, type):
        return type(value) is rule
    if rule == "point":
        return point(value)
    if rule == "rect":
        return isinstance(value, list) and len(value) == 4 and all(type(v) is int for v in value)
    if rule == "points":
        return isinstance(value, list) and 2 <= len(value) <= 10000 and all(point(v) for v in value)
    if rule == "nullable_text":
        return value is None or isinstance(value, str)
    if rule == "properties":
        return isinstance(value, list) and len(value) <= 512 and all(
            isinstance(prop, dict) and set(prop) == {"name", "value"} and isinstance(prop["name"], str)
            and prop["name"] and isinstance(prop["value"], str) for prop in value
        ) and len({prop["name"] for prop in value}) == len(value)
    return False


def validate_inventory(data, baseline, mode):
    try:
        if mode not in MODES or not isinstance(data, dict) or set(data) != {"schematic", "page", "objects"}:
            raise ValueError("Invalid inventory document shape")
        for kind in ("schematic", "page"):
            expected = [{key: val for key, val in row.items() if key != "generation"} for row in baseline[kind]]
            if data[kind] != expected:
                raise ValueError("Inventory definition parents differ from snapshot")
        rows = data["objects"]
        if not isinstance(rows, list) or len(rows) > 100000:
            raise ValueError("Invalid inventory count")
        pages = {row["objectId"] for row in baseline["page"]}
        parts = {row["objectId"]: row for row in baseline["part"]}
        pins = {row["objectId"]: row for row in baseline["pin"]}
        by_id = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"kind", "objectId", "pageId", "nativeId", "objectType", "attributes"}:
                raise ValueError("Invalid inventory object shape")
            if row["kind"] not in MODES[mode] or not isinstance(row["objectId"], str) or not row["objectId"] or row["objectId"] in by_id:
                raise ValueError("Invalid inventory identity")
            if row["pageId"] not in pages or type(row["nativeId"]) is not int or type(row["objectType"]) is not int:
                raise ValueError("Invalid inventory parent/native attributes")
            attrs = row["attributes"]
            schema = ATTRIBUTES[row["kind"]]
            if not isinstance(attrs, dict) or set(attrs) != set(schema) or any(not value_valid(attrs[key], rule) for key, rule in schema.items()):
                raise ValueError("Invalid inventory attributes")
            if "partId" in attrs:
                parent = parts.get(attrs["partId"])
                if parent is None or parent["pageId"] != row["pageId"] or ("reference" in attrs and parent["reference"] != attrs["reference"]):
                    raise ValueError("Invalid part-linked object")
            if row["kind"] == "nc":
                pin = pins.get(attrs["pinId"])
                if pin is None or pin["partId"] != attrs["partId"] or pin["number"] != attrs["number"]:
                    raise ValueError("NC pin identity mismatch")
            by_id[row["objectId"]] = row
        for row in rows:
            if row["kind"] == "alias":
                wire = by_id.get(row["attributes"]["wireId"])
                if wire is None or wire["kind"] != "wire" or wire["pageId"] != row["pageId"]:
                    raise ValueError("Alias wire identity mismatch")
    except (ValueError, KeyError, TypeError) as error:
        raise CadenceError("invalid_worker_result", "Invalid page object inventory.", "decode") from error


def query_objects(capture, session_id, mode, entity, page_id, cursor, limit):
    with capture.lock:
        session = capture._session(session_id)
        if mode not in MODES or entity not in MODES[mode] or type(limit) is not int or not 1 <= limit <= 1000:
            raise CadenceError("invalid_query", "Invalid page object category/entity/page size.")
        if page_id is not None and page_id not in {row["objectId"] for row in session["data"]["page"]}:
            raise CadenceError("invalid_scope", "Page does not belong to this immutable session.")
        cache = session.setdefault("objectInventories", {})
        if mode not in cache:
            directory = checked_path(str(capture._workspace(session["workspaceId"])["directory"]), (capture.config.workspace_root,))
            output = directory / f"{new_id('page-objects')}.json"
            run_tcl(capture.config, "inspect_page_objects.tcl", [str(session["design"]), str(output), mode], directory)
            capture._session(session_id)
            try:
                if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Missing or oversized object inventory")
                data = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise CadenceError("invalid_worker_result", "Invalid page inventory output.", "decode") from error
            validate_inventory(data, session["data"], mode)
            output.unlink()
            cache[mode] = data["objects"]
        cursors = session.setdefault("objectInventoryCursors", {})
        signature = (mode, entity, page_id, limit)
        offset = 0
        if cursor is not None:
            saved = cursors.get(cursor)
            if saved is None or saved[0] != signature:
                raise CadenceError("stale_cursor", "Object cursor is bound to its session/query/page size.")
            offset = saved[1]
        rows = [row for row in cache[mode] if row["kind"] == entity and (page_id is None or row["pageId"] == page_id)]
        next_cursor = None
        if offset + limit < len(rows):
            if len(cursors) >= 10000:
                raise CadenceError("cursor_limit", "Too many object cursors; open a new session.")
            next_cursor = new_id("object-cursor")
            cursors[next_cursor] = (signature, offset + limit)
        return {"sessionId": session_id, "revision": session["revision"], "scope": "design_definitions",
                "items": rows[offset:offset + limit], "total": len(rows), "nextCursor": next_cursor,
                "complete": next_cursor is None, "inventoryCounts": dict(Counter(row["kind"] for row in cache[mode])),
                "units": "capture_native_integer", "electricalConnectivityVerified": False,
                "displayLocationSpace": "owner_local", "displayBoundsSpace": "native_cached_unverified",
                "notChecked": ["junction_connectivity", "occurrence_connectivity", "bus_member_connectivity", "native_drc",
                               "rendered_bounds_validity", "display_bounds_coordinate_space"]}
