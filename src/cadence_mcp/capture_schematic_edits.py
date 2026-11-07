"""Guarded schematic lifecycle on isolated design copies."""
import copy
import json

from .capture_design_create import COUNT_KEYS, design_name, read_document_meta
from .capture_edit import definition_baseline
from .capture_objects import read_inventory
from .capture_page_edit import CapturePageEdits
from .capture_wire import inventory
from .core import CadenceError
from .environment import ADAPTERS
from .isolated_jobs import digest
from .schematic_dependencies import require_unreferenced, schematic_dependencies


def dependency_digest(graph):
    # Definition traversal IDs can shift when a schematic is inserted or removed.
    def stable(rows):
        return sorted(
            [{key: value for key, value in row.items() if key != "partId"} for row in rows],
            key=lambda row: json.dumps(row, sort_keys=True),
        )

    return digest({"incoming": {key: stable(rows) for key, rows in graph["incoming"].items()},
                   "unresolved": stable(graph["unresolved"])})


def ascii_name(name):
    name = design_name(name)
    if not name.isascii():
        raise CadenceError("unsupported_design_encoding", "Non-ASCII document writes have not passed native save/reopen.")
    return name


class CaptureSchematicEdits(CapturePageEdits):
    kind = "capture_schematic_edit"

    def plan(self, sid, operation, schematic_id, name, page_name):
        if operation not in self.operations:
            raise CadenceError("invalid_schematic_change", "Unsupported schematic operation.")
        if operation == "create":
            if schematic_id is not None:
                raise CadenceError("invalid_schematic_change", "Creation takes a new schematic and page name.")
            page_name = ascii_name(page_name)
        elif page_name is not None:
            raise CadenceError("invalid_schematic_change", "Only creation takes a page name.")
        if operation == "delete":
            if name is not None:
                raise CadenceError("invalid_schematic_change", "Deletion takes a schematic ID and no new name.")
        else:
            name = ascii_name(name)

        with self.capture.lock:
            session = self.capture._session(sid)
            data = session["data"]
            expected = copy.deepcopy(data)
            meta = read_document_meta(self.config, session["design"], session["design"].parent)
            graph = schematic_dependencies(self.capture, sid)
            names = graph["incoming"]
            if operation != "delete" and any(name.casefold() == old.casefold() for old in names):
                raise CadenceError("schematic_name_conflict", "Schematic name already exists, ignoring case.")
            connections = inventory(self.capture, sid)
            graphics = read_inventory(self.capture, sid, "graphics", titleblock_users=True)
            old_name = ""
            if operation == "create":
                if graph["unresolved"]:
                    raise CadenceError("schematic_dependencies_unverified", "Unresolved implementations could bind to the new name.")
                expected["schematic"].append({"objectId": "new-schematic", "name": name})
                expected["page"].append({"objectId": "new-page", "schematicId": "new-schematic", "name": page_name})
                meta["schematics"].append({"name": name})
                meta["pages"].append({"schematicName": name, "name": page_name, "counts": dict.fromkeys(COUNT_KEYS, 0)})
                names[name] = []
            else:
                target = next((row for row in expected["schematic"] if row["objectId"] == schematic_id), None)
                if target is None:
                    raise CadenceError("object_not_found", "Schematic does not belong to this immutable session.")
                old_name = target["name"]
                if old_name.casefold() == meta["rootName"].casefold():
                    raise CadenceError("root_schematic_protected", "The root schematic cannot be renamed or deleted by this task.")
                require_unreferenced(graph, old_name)
                native_pages = [row for row in meta["pages"] if row["schematicName"] == old_name]
                page_ids = {row["objectId"] for row in data["page"] if row["schematicId"] == schematic_id}
                definition_names = {row["name"] for row in data["page"] if row["objectId"] in page_ids}
                if definition_names != {row["name"] for row in native_pages}:
                    raise CadenceError("schematic_page_mismatch", "Native and definition page lists disagree.")
                if any(any(row["counts"].values()) for row in native_pages) or any(
                    row["pageId"] in page_ids for rows in (data["part"], connections, graphics) for row in rows
                ):
                    raise CadenceError("schematic_not_empty", "This task requires every page of the target schematic to be empty.")
                del names[old_name]
                if operation == "rename":
                    target["name"] = name
                    next(row for row in meta["schematics"] if row["name"] == old_name)["name"] = name
                    for row in native_pages:
                        row["schematicName"] = name
                    names[name] = []
                else:
                    expected["schematic"].remove(target)
                    expected["page"] = [row for row in expected["page"] if row["objectId"] not in page_ids]
                    meta["schematics"] = [row for row in meta["schematics"] if row["name"] != old_name]
                    meta["pages"] = [row for row in meta["pages"] if row["schematicName"] != old_name]
            payload = {"sourceDesign": str(session["design"]), "sourceFingerprint": session["revision"],
                       "operation": operation, "schematicName": old_name or name, "oldName": old_name,
                       "name": name or "", "pageName": page_name or "",
                       "expectedDefinitionDigest": definition_baseline(expected), "dependencyDigest": dependency_digest(graph)}
            return self.create_plan(self.freeze_content(sid, session, data, expected, payload, connections, graphics, meta))

    def preview(self, payload):
        return {**super().preview(payload), "pageName": payload["pageName"]}

    def native_command(self, directory, payload):
        return [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "edit_schematic.tcl",
                self.config.install_root, directory / "design.dsn", directory / "native-result.json",
                payload["operation"], payload["schematicName"], payload["name"], payload["pageName"]]

    def verify_content(self, verifier, sid, payload):
        super().verify_content(verifier, sid, payload)
        if dependency_digest(schematic_dependencies(verifier, sid)) != payload["dependencyDigest"]:
            raise CadenceError("schematic_dependency_mismatch", "Saved schematic dependencies differ from the explicit plan.", "verify")

    def verify(self, directory, payload, native_completed):
        result = super().verify(directory, payload, native_completed)
        result["artifact"]["artifactId"] = "schematic-" + result["planId"]
        result["definitionDependenciesVerified"] = True
        result["notChecked"].remove("hierarchy_dependencies")
        return result
