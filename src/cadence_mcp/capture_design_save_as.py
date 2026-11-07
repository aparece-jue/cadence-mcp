"""Native SaveDesignAs with a named, independently verified owned output."""
import re
import shutil

from .capture_design_create import read_document_meta
from .capture_edit import definition_baseline, read_design_properties
from .capture_objects import read_inventory
from .capture_page_edit import CapturePageEdits
from .capture_schematic_edits import dependency_digest
from .capture_wire import inventory
from .core import CadenceError, checked_path, sha256
from .environment import ADAPTERS, process_env
from .isolated_jobs import digest
from .process_tree import run_owned_process
from .schematic_dependencies import schematic_dependencies


def design_file_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_. -]{0,63}\.dsn", value, re.ASCII | re.IGNORECASE):
        raise CadenceError("invalid_design_file_name", "Use a simple ASCII DSN basename, including the .dsn extension.")
    stem = value[:-4]
    device = stem.split(".", 1)[0].rstrip().upper()
    if stem.endswith((".", " ")) or re.fullmatch(r"CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]", device):
        raise CadenceError("invalid_design_file_name", "Windows reserved basenames and trailing spaces or dots are refused.")
    return value


class CaptureDesignSaves(CapturePageEdits):
    kind = "capture_design_save_as"
    operations = ("save_as",)

    def plan(self, sid, file_name):
        name = design_file_name(file_name)
        with self.capture.lock:
            session = self.capture._session(sid)
            design = session["design"]
            data = session["data"]
            meta = read_document_meta(self.config, design, design.parent)
            graph = schematic_dependencies(self.capture, sid)
            if graph["unresolved"]:
                raise CadenceError("schematic_dependencies_unverified", "External or unresolved implementations cannot be relocated by this task.")
            payload = {"sourceDesign": str(design), "sourceFingerprint": session["revision"],
                       "operation": "save_as", "schematicName": meta["rootName"], "oldName": "",
                       "name": name, "expectedDefinitionDigest": definition_baseline(data),
                       "dependencyDigest": dependency_digest(graph),
                       "propertiesDigest": digest(read_design_properties(self.config, design, design.parent))}
            connections = inventory(self.capture, sid)
            graphics = read_inventory(self.capture, sid, "graphics", titleblock_users=True)
            return self.create_plan(self.freeze_content(sid, session, data, data, payload, connections, graphics, meta))

    def preview(self, payload):
        return {"operation": "save_as", "fileName": payload["name"], "rootName": payload["schematicName"],
                "sourceFingerprint": payload["sourceFingerprint"]}

    def design_relative_path(self, payload):
        return design_file_name(payload["name"])

    def preflight(self, payload):
        self.design_relative_path(payload)
        super().preflight(payload)

    def execute(self, directory, payload, cancel, on_started):
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        output = directory / self.design_relative_path(payload)
        if output.exists() or output.is_symlink():
            raise CadenceError("output_exists", "An existing Save As output must never be overwritten.")
        stage = directory / "source-snapshot"
        stage.mkdir()
        copy = stage / "design.dsn"
        with source.open("rb") as original, copy.open("xb") as staged:
            shutil.copyfileobj(original, staged)
        self.preflight(payload)
        self.verify_source_copy(directory, payload)
        return run_owned_process(
            [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "save_design_as.tcl",
             self.config.install_root, copy, output, directory / "native-result.json", payload["schematicName"]],
            directory, process_env(self.config), self.config.timeout_seconds, cancel=cancel, on_started=on_started,
        )

    def verify_source_copy(self, directory, payload):
        path = checked_path(str(directory / "source-snapshot/design.dsn"), (directory,))
        if path != directory / "source-snapshot/design.dsn" or sha256(path) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "The Save As source snapshot differs from the plan.")

    def verify_content(self, verifier, sid, payload):
        super().verify_content(verifier, sid, payload)
        design = verifier._session(sid)["design"]
        if dependency_digest(schematic_dependencies(verifier, sid)) != payload["dependencyDigest"]:
            raise CadenceError("schematic_dependency_mismatch", "Saved definition dependencies differ from the source.", "verify")
        if digest(read_design_properties(self.config, design, design.parent)) != payload["propertiesDigest"]:
            raise CadenceError("unexpected_property_change", "Saved effective instance properties differ from the source.", "verify")

    def verify(self, directory, payload, native_completed):
        self.verify_source_copy(directory, payload)
        result = super().verify(directory, payload, native_completed)
        self.verify_source_copy(directory, payload)
        result["artifact"]["artifactId"] = "save-as-" + result["planId"]
        result.update(definitionDependenciesVerified=True, effectiveInstancePropertiesVerified=True, sourceSnapshotUnchanged=True)
        result["notChecked"].remove("hierarchy_dependencies")
        result["notChecked"].append("external_project_and_simulation_resources")
        return result
