"""Immutable, read-only design-definition sessions over isolated Tcl workers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import threading

from .core import CadenceError, Config, checked_path, new_id, sha256, write_json
from .environment import run_tcl

FIELDS = {
    "schematic": {"objectId", "name", "generation"},
    "page": {"objectId", "schematicId", "name", "generation"},
    "part": {"objectId", "pageId", "schematicId", "reference", "generation"},
    "pin": {"objectId", "partId", "pageId", "schematicId", "reference", "number", "name", "connected", "net", "generation"},
}


class CaptureService:
    def __init__(self, config: Config):
        self.config = config
        self.workspaces: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.lock = threading.RLock()

    def create_workspace(self, source_design: str) -> dict:
        with self.lock:
            source = checked_path(source_design, self.config.read_roots)
            if not source.is_file() or source.suffix.lower() != ".dsn":
                raise CadenceError("unsupported_input", "Phase 1 accepts one DSN design file only; not OPJ/OLB.")
            if source.stat().st_size > 128 * 1024 * 1024:
                raise CadenceError("input_limit", "Design exceeds the 128 MiB input limit.")
            before = sha256(source)
            workspace_id = new_id("ws")
            directory = self.config.workspace_root / workspace_id
            directory.mkdir()
            directory = checked_path(str(directory), (self.config.workspace_root,))
            copied = directory / "design.dsn"
            shutil.copyfile(source, copied)
            if sha256(source) != before or sha256(copied) != before:
                raise CadenceError("source_changed", "Source changed during copy; discard this workspace.")
            manifest = {
                "workspaceId": workspace_id, "sourcePath": str(source), "sourceFingerprint": before,
                "designRelativePath": "design.dsn", "copiedFingerprint": before,
                "copyMode": "single_design_file", "dependencyClosureVerified": False,
                "notCopied": ["external libraries", "hierarchical external designs", "PSpice profiles/models"],
            }
            write_json(directory / "manifest.json", manifest)
            self.workspaces[workspace_id] = {"directory": directory, "manifest": manifest}
            return manifest

    def _workspace(self, workspace_id: str) -> dict:
        if workspace_id not in self.workspaces:
            raise CadenceError("workspace_not_found", "Workspace is not registered in this server instance.")
        return self.workspaces[workspace_id]

    def open(self, workspace_id: str) -> dict:
        with self.lock:
            workspace = self._workspace(workspace_id)
            directory = checked_path(str(workspace["directory"]), (self.config.workspace_root,))
            design = checked_path(str(directory / "design.dsn"), (directory,))
            if sha256(design) != workspace["manifest"]["copiedFingerprint"]:
                raise CadenceError("target_changed", "The workspace design changed; create a new workspace.")
            before = sha256(design)
            output = directory / f"{new_id('inspection')}.json"
            try:
                run_tcl(self.config, "inspect.tcl", [str(design), str(output), "100000"], directory)
                if sha256(design) != before:
                    raise CadenceError("target_changed", "The copied design changed while inspecting it.")
                if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                    raise CadenceError("output_limit", "No bounded inspection result was produced.", "decode")
                data = json.loads(output.read_text(encoding="utf-8"))
                if set(data) != set(FIELDS) or any(not isinstance(data[k], list) for k in FIELDS):
                    raise ValueError("Unexpected worker shape")
                if sum(len(rows) for rows in data.values()) > 100000:
                    raise ValueError("Unexpected object count")
                for entity, rows in data.items():
                    ids = set()
                    for row in rows:
                        if not isinstance(row, dict) or set(row) != FIELDS[entity] - {"generation"}:
                            raise ValueError("Unexpected worker fields")
                        if row["objectId"] in ids:
                            raise ValueError("Duplicate worker identity")
                        ids.add(row["objectId"])
                        if any(not isinstance(v, str) for k, v in row.items() if k != "connected"):
                            raise ValueError("Unexpected worker value")
                        if entity == "pin" and not isinstance(row["connected"], bool):
                            raise ValueError("Unexpected connection status")
                        row["generation"] = 1
            except (OSError, ValueError, json.JSONDecodeError) as e:
                raise CadenceError("invalid_worker_result", "Worker returned an invalid inspection document.", "decode") from e
            session_id = new_id("s")
            self.sessions[session_id] = {"workspaceId": workspace_id, "design": design,
                                         "revision": before, "data": data, "cursors": {}}
            return {"sessionId": session_id, "workspaceId": workspace_id, "generation": 1,
                    "revision": before, "readOnly": True, "backend": "standalone",
                    "scope": "design_definitions", "counts": {k: len(v) for k, v in data.items()},
                    "occurrenceConnectivityVerified": False}

    def _session(self, session_id: str) -> dict:
        if session_id not in self.sessions:
            raise CadenceError("session_lost", "Session is closed or belongs to a previous server instance.")
        session = self.sessions[session_id]
        workspace = self._workspace(session["workspaceId"])
        design = checked_path(str(session["design"]), (workspace["directory"],))
        if sha256(design) != session["revision"]:
            raise CadenceError("target_changed", "Design fingerprint changed; this immutable session is stale.")
        return session

    def query(self, session_id: str, entity: str, scope: dict, fields: list[str] | None,
              reference: str | None, cursor: str | None, limit: int) -> dict:
        with self.lock:
            session = self._session(session_id)
            if entity not in FIELDS or not 1 <= limit <= 1000:
                raise CadenceError("invalid_query", "Unsupported entity or page size.")
            if fields is not None and (not fields or len(fields) != len(set(fields)) or set(fields) - FIELDS[entity]):
                raise CadenceError("invalid_query", "Unknown, empty or duplicate field selection.")
            page_id = scope.get("pageId")
            if scope.get("kind") == "page":
                if entity == "schematic" or page_id not in {r["objectId"] for r in session["data"]["page"]}:
                    raise CadenceError("invalid_scope", "Unknown page or incompatible entity.")
            elif scope != {"kind": "design"}:
                raise CadenceError("capability_unavailable", "Only design-definition and page scopes are implemented.")
            if reference is not None and entity not in ("part", "pin"):
                raise CadenceError("invalid_query", "Reference filtering applies only to parts or pins.")
            signature = json.dumps([entity, scope, fields, reference, limit], sort_keys=True)
            offset = 0
            if cursor is not None:
                saved = session["cursors"].get(cursor)
                if saved is None or saved[0] != signature:
                    raise CadenceError("stale_cursor", "Cursor does not belong to this query and session.")
                offset = saved[1]
            rows = session["data"][entity]
            if page_id is not None:
                rows = [r for r in rows if (r["objectId"] if entity == "page" else r.get("pageId")) == page_id]
            if reference is not None:
                rows = [r for r in rows if r["reference"] == reference]
            page = rows[offset:offset + limit]
            if fields is not None:
                page = [{k: row[k] for k in fields} for row in page]
            next_cursor = None
            if offset + limit < len(rows):
                if len(session["cursors"]) >= 10000:
                    raise CadenceError("cursor_limit", "Session cursor limit reached; open a new session.")
                next_cursor = new_id("cursor")
                session["cursors"][next_cursor] = (signature, offset + limit)
            return {"items": page, "nextCursor": next_cursor, "complete": next_cursor is None,
                    "total": len(rows), "revision": session["revision"], "coverage": "design_definitions"}

    def snapshot(self, session_id: str) -> dict:
        with self.lock:
            session = self._session(session_id)
            workspace = self._workspace(session["workspaceId"])
            directory = checked_path(str(workspace["directory"]), (self.config.workspace_root,))
            snapshot_id = new_id("snapshot")
            target = directory / f"{snapshot_id}.json"
            payload = {"snapshotId": snapshot_id, "sessionId": session_id, "generation": 1,
                       "revision": session["revision"], "scope": "design_definitions", "objects": session["data"],
                       "occurrenceConnectivityVerified": False}
            write_json(target, payload)
            artifact = {"artifactId": snapshot_id, "kind": "capture_snapshot",
                        "workspaceRelativePath": target.name, "sha256": sha256(target),
                        "size": target.stat().st_size, "producedByJob": new_id("sync"),
                        "sourceFingerprint": session["revision"],
                        "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "unverified"}
            return {"snapshotId": snapshot_id, "workspaceId": session["workspaceId"], "artifact": artifact}


    def check_wiring(self, session_id: str, grid_size=None, grid_origin=None) -> dict:
        """Inspect current copied definitions in a new worker; no GUI or PDF."""
        from .wiring import analyze_wiring,grid_options
        grid_options(grid_size,grid_origin)
        with self.lock:
            session = self._session(session_id)
            workspace = self._workspace(session["workspaceId"])
            directory = checked_path(str(workspace["directory"]), (self.config.workspace_root,))
            raw = directory / f"{new_id('wire-geometry')}.json"
            run_tcl(self.config, "inspect_geometry.tcl", [str(session["design"]), str(raw), "100000"], directory)
            self._session(session_id)  # Reject external edits during inspection.
            try:
                if not raw.is_file() or raw.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Missing or oversized geometry document")
                geometry = json.loads(raw.read_text(encoding="utf-8"))
                report = analyze_wiring(geometry,grid_size,grid_origin)
            except (OSError, ValueError) as error:
                raise CadenceError("invalid_worker_result", "Invalid wire inspection document.", "decode") from error
            artifact_id = new_id("wiring-report")
            destination = directory / f"{artifact_id}.json"
            report.update({"revision": session["revision"], "sessionId": session_id,
                           "geometryDocument": raw.name, "geometrySha256": sha256(raw),
                           "pdfRequired": False})
            write_json(destination, report)
            artifact = {"artifactId": artifact_id, "kind": "capture_wiring_report",
                        "workspaceRelativePath": destination.name, "sha256": sha256(destination),
                        "size": destination.stat().st_size, "producedByJob": new_id("sync"),
                        "sourceFingerprint": session["revision"],
                        "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "unverified"}
            return {**report, "artifact": artifact}

    def compare_connections(self, session_id: str, expected_revision: str,
                            expectations: list[dict], expectation_source: str) -> dict:
        """Compare independently specified expectations; never derive an expected table."""
        from .connections import compare_connections
        with self.lock:
            session = self._session(session_id)
            if expected_revision != session["revision"]:
                raise CadenceError("target_changed", "Expected revision does not match this immutable session.")
            report = compare_connections(session["data"], expectations, expectation_source)
            directory = checked_path(str(self._workspace(session["workspaceId"])["directory"]),
                                     (self.config.workspace_root,))
            report.update({"revision": session["revision"], "sessionId": session_id, "pdfRequired": False})
            artifact_id = new_id("connection-report")
            destination = directory / f"{artifact_id}.json"
            write_json(destination, report)
            artifact = {"artifactId": artifact_id, "kind": "capture_connection_report",
                        "workspaceRelativePath": destination.name, "sha256": sha256(destination),
                        "size": destination.stat().st_size, "producedByJob": new_id("sync"),
                        "sourceFingerprint": session["revision"],
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "validationState": "unverified"}
            return {**report, "artifact": artifact}

    def close(self, session_id: str) -> dict:
        with self.lock:
            # Closing a stale session must still release its cached data.
            if session_id not in self.sessions:
                raise CadenceError("session_lost", "Session is already closed or unknown.")
            del self.sessions[session_id]
            return {"sessionId": session_id, "closed": True, "saved": False}
