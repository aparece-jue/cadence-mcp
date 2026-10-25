"""Read-only copied OLBs; device-scoped logical/physical pin mapping."""
from pathlib import Path
import json
import shutil
import threading

from .core import CadenceError, checked_path, new_id, sha256, write_json
from .environment import run_tcl


FIELDS = {
    "package": {"objectId": str, "name": str, "size": int, "homogeneous": bool, "footprint": str},
    "device": {"objectId": str, "packageId": str, "designator": str, "position": int, "cellId": str},
    "cell": {"objectId": str, "deviceId": str, "packageId": str, "name": str},
    "part": {"objectId": str, "cellId": str, "deviceId": str, "packageId": str, "name": str},
    "pin": {"objectId": str, "partId": str, "deviceId": str, "packageId": str, "name": str,
            "position": int, "number": str, "pinType": int, "visible": bool,
            "shared": bool, "swapId": int, "hotSpot": list},
}


def validate_library(data: dict) -> None:
    try:
        if not isinstance(data, dict) or set(data) != set(FIELDS):
            raise ValueError("Invalid library document shape")
        all_ids = set()
        for kind, schema in FIELDS.items():
            rows = data[kind]
            if not isinstance(rows, list):
                raise ValueError("Invalid library rows")
            for row in rows:
                if not isinstance(row, dict) or set(row) != set(schema):
                    raise ValueError("Invalid library fields")
                if any(type(row[key]) is not value_type for key, value_type in schema.items()):
                    raise ValueError("Invalid library value")
                if not row["objectId"] or row["objectId"] in all_ids:
                    raise ValueError("Duplicate library identity")
                all_ids.add(row["objectId"])
                if kind == "pin" and (len(row["hotSpot"]) != 2 or any(type(v) is not int for v in row["hotSpot"])):
                    raise ValueError("Invalid pin hotspot")
        if len(all_ids) > 100000:
            raise ValueError("Too many library objects")
        by_kind = {kind: {row["objectId"]: row for row in rows} for kind, rows in data.items()}
        for kind, rows in data.items():
            for row in rows:
                for parent in ("package", "device", "cell", "part"):
                    key = f"{parent}Id"
                    if key in row and row[key] not in by_kind[parent]:
                        raise ValueError("Missing library parent")
                if kind in ("cell", "part", "pin"):
                    device = by_kind["device"][row["deviceId"]]
                    if device["packageId"] != row["packageId"]:
                        raise ValueError("Library package mismatch")
                    if kind == "cell" and device["cellId"] != row["objectId"]:
                        raise ValueError("Library cell mismatch")
                    if kind == "part" and device["cellId"] != row["cellId"]:
                        raise ValueError("Library part mismatch")
                    if kind == "pin":
                        part = by_kind["part"][row["partId"]]
                        if part["deviceId"] != row["deviceId"] or part["packageId"] != row["packageId"]:
                            raise ValueError("Library pin mismatch")
    except (KeyError, ValueError, TypeError) as error:
        raise CadenceError("invalid_worker_result", "Invalid library inspection document.", "decode") from error


class LibraryService:
    def __init__(self, config):
        self.config = config
        self.sessions = {}
        self.lock = threading.RLock()

    def open(self, source_library: str) -> dict:
        with self.lock:
            if len(self.sessions) >= 32:
                raise CadenceError("session_limit", "Close an existing library session first.")
            source = checked_path(source_library, self.config.read_roots)
            if not source.is_file() or source.suffix.lower() != ".olb":
                raise CadenceError("unsupported_input", "Library tools accept one OLB file only.")
            if source.stat().st_size > 128 * 1024 * 1024:
                raise CadenceError("input_limit", "Library exceeds 128 MiB.")
            revision = sha256(source)
            library_id = new_id("lib")
            directory = self.config.workspace_root / library_id
            directory.mkdir()
            directory = checked_path(str(directory), (self.config.workspace_root,))
            copied = directory / "library.olb"
            shutil.copyfile(source, copied)
            if sha256(source) != revision or sha256(copied) != revision:
                raise CadenceError("source_changed", "Library changed during copy.")
            output = directory / "inspection.json"
            run_tcl(self.config, "inspect_library.tcl", [str(copied), str(output), "100000"], directory)
            if sha256(copied) != revision:
                raise CadenceError("target_changed", "Copied library changed during read.")
            try:
                if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Invalid library output size")
                data = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise CadenceError("invalid_worker_result", "Invalid library inspection document.", "decode") from error
            validate_library(data)
            manifest = {"libraryId": library_id, "sourceFingerprint": revision, "revision": revision,
                        "copyMode": "single_library_file", "sourcePath": str(source),
                        "libraryRelativePath": copied.name, "counts": {kind: len(rows) for kind, rows in data.items()},
                        "readOnly": True, "scope": "library_device_definitions",
                        "externalFootprintVerified": False}
            write_json(directory / "manifest.json", manifest)
            self.sessions[library_id] = {"directory": directory, "revision": revision, "data": data, "cursors": {}}
            return manifest

    def _session(self, library_id):
        session = self.sessions.get(library_id)
        if session is None:
            raise CadenceError("session_lost", "Library session is unknown or closed.")
        directory = checked_path(str(session["directory"]), (self.config.workspace_root,))
        copied = checked_path(str(directory / "library.olb"), (directory,))
        if sha256(copied) != session["revision"]:
            raise CadenceError("target_changed", "Library copy changed; open a fresh session.")
        return session

    def query(self, library_id: str, entity: str, package_name: str | None, cursor: str | None, limit: int) -> dict:
        with self.lock:
            session = self._session(library_id)
            if entity not in FIELDS or type(limit) is not int or not 1 <= limit <= 1000:
                raise CadenceError("invalid_query", "Invalid library entity or page size.")
            signature = json.dumps([entity, package_name, limit], ensure_ascii=False)
            offset = 0
            if cursor is not None:
                saved = session["cursors"].get(cursor)
                if saved is None or saved[0] != signature:
                    raise CadenceError("stale_cursor", "Library cursor does not belong to this query.")
                offset = saved[1]
            rows = session["data"][entity]
            if package_name is not None:
                ids = {row["objectId"] for row in session["data"]["package"] if row["name"] == package_name}
                rows = [row for row in rows if row["objectId"] in ids] if entity == "package" else [row for row in rows if row["packageId"] in ids]
            items = rows[offset:offset + limit]
            next_cursor = None
            if offset + limit < len(rows):
                if len(session["cursors"]) >= 10000:
                    raise CadenceError("cursor_limit", "Too many library cursors; open a fresh session.")
                next_cursor = new_id("libcursor")
                session["cursors"][next_cursor] = (signature, offset + limit)
            return {"libraryId": library_id, "revision": session["revision"], "items": items,
                    "total": len(rows), "nextCursor": next_cursor, "complete": next_cursor is None,
                    "scope": "library_device_definitions"}

    def close(self, library_id: str) -> dict:
        with self.lock:
            if library_id not in self.sessions:
                raise CadenceError("session_lost", "Library session is already closed or unknown.")
            del self.sessions[library_id]
            return {"libraryId": library_id, "closed": True, "saved": False}
