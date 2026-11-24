"""Revision-bound titleblock field observations and native owner context."""
import json

from .capture_titleblock_vectors import titleblock_target
from .core import CadenceError, new_id
from .environment import run_tcl


def compare_field(value, context):
    if value in (0, ""):
        return "unavailable"
    if context in (0, ""):
        return "uncorroborated"
    return "matches_context" if value == context else "differs_from_context"


def normalize_fields(row, target, owner_count):
    text_fields = {"name", "designName", "designFileName", "sourceSymbol", "pageSize", "ownerSizeName"}
    int_fields = {"nativeId", "pageCount", "pageNumber", "ownerPageNumber"}
    if (not isinstance(row, dict) or set(row) != text_fields | int_fields
            or any(type(row[key]) is not str or len(row[key]) > 4096 or "\x00" in row[key] for key in text_fields)
            or any(type(row[key]) is not int or not 0 <= row[key] <= 4294967295 for key in int_fields)
            or row["nativeId"] != target["nativeId"] or row["name"] != target["attributes"]["name"]):
        raise CadenceError("invalid_worker_result", "Invalid titleblock field document.", "decode")
    context = {"schematicPageCount": owner_count, "pageNumber": row["ownerPageNumber"],
               "pageSizeName": row["ownerSizeName"]}
    native = {key: row[key] for key in text_fields | {"pageCount", "pageNumber"}}
    fields = {name: compare_field(native[name], context[field]) for name, field in
              (("pageCount", "schematicPageCount"), ("pageNumber", "pageNumber"), ("pageSize", "pageSizeName"))}
    return native, context, fields


def normalize_bounds(row):
    keys = {"localBounds", "offsetBounds", "symbolBounds", "dirty"}
    if (not isinstance(row, dict) or set(row) != keys or type(row["dirty"]) is not int
            or row["dirty"] not in (0, 1)
            or any(type(row[key]) is not list or len(row[key]) != 4
                   or any(type(n) is not int or not -(2**31) <= n < 2**31 for n in row[key])
                   for key in keys - {"dirty"})):
        raise CadenceError("invalid_worker_result", "Invalid native titleblock bounds.", "decode")
    degenerate = any(row[key][2] <= row[key][0] or row[key][3] <= row[key][1]
                     for key in keys - {"dirty"})
    status = "dirty_cache" if row["dirty"] else "degenerate_cache" if degenerate else "clean_cache_unverified"
    return {**row, "dirty": bool(row["dirty"]), "degenerate": degenerate,
            "cacheStatus": status, "renderedBoundsVerified": False}


def query_titleblock_fields(capture, sid, target_id):
    with capture.lock:
        session = capture._session(sid)
        target, page, schematic = titleblock_target(capture, sid, target_id)
        directory = session["design"].parent
        out = directory / (new_id("titleblock-fields") + ".json")
        run_tcl(capture.config, "inspect_titleblock_fields.tcl",
                [str(session["design"]), str(out), schematic["name"], page["name"], str(target["nativeId"])], directory)
        capture._session(sid)
        try:
            if not out.is_file() or out.stat().st_size > 65536:
                raise ValueError("Invalid output size")
            raw = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CadenceError("invalid_worker_result", "Invalid bounded titleblock output.", "decode") from error
        owner_count = sum(row["schematicId"] == schematic["objectId"] for row in session["data"]["page"])
        if not isinstance(raw, dict) or "boundingBoxObservation" not in raw:
            raise CadenceError("invalid_worker_result", "Missing titleblock bounds observation.", "decode")
        bounds = normalize_bounds(raw["boundingBoxObservation"])
        native, context, fields = normalize_fields(
            {key: value for key, value in raw.items() if key != "boundingBoxObservation"}, target, owner_count)
        out.unlink()
        return {"sessionId": sid, "revision": session["revision"], "titleblockId": target_id,
                "pageId": page["objectId"], "schematicName": schematic["name"], "pageName": page["name"],
                "nativeTitleblockFields": native, "ownerPageContext": context, "fieldStatus": fields,
                "nativeBoundingBox": bounds,
                "allGeneratedPageFieldsMatchContext": all(status == "matches_context" for status in fields.values()),
                "renderedTextVerified": False, "scope": "titleblock_definition_and_owner_page_context"}
