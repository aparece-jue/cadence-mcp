"""Verify E04 schematic dependencies against SPB 24.1 before fixed private edits."""
import argparse
import json
from pathlib import Path
import shutil

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_design_create import read_document_meta
from cadence_mcp.core import CadenceError, Config, sha256, write_json
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.schematic_dependencies import require_unreferenced, schematic_dependencies


def run(install, sample, output):
    output.mkdir(parents=True, exist_ok=False)
    config = Config(install, output / "work", (sample.parent, output), 60)
    capture = CaptureService(config)
    before = sha256(sample)

    def snapshot(design):
        ws = capture.create_workspace(str(design))
        sid = capture.open(ws["workspaceId"])["sessionId"]
        try:
            session = capture._session(sid)
            data = session["data"]
            names = {row["objectId"]: row["name"] for row in data["schematic"]}
            meta = read_document_meta(config, session["design"], session["design"].parent)
            pages = sorted((names[row["schematicId"]], row["name"]) for row in data["page"])
            return sorted(names.values()), pages, meta, schematic_dependencies(capture, sid)
        finally:
            capture.close(sid)

    def execute(operation, source=None):
        directory = output / operation
        directory.mkdir()
        target = directory / "design.dsn"
        if source is not None:
            shutil.copyfile(source, target)
        result = run_owned_process(
            [install / "tcltk/bin/tclsh.exe", ADAPTERS / "document_probe.tcl",
             install, target, directory / "native-result.json", operation],
            directory, process_env(config), 60,
        )
        assert result["returnCode"] == 0 and result["remainingOwnedProcesses"] == 0, (operation, result)
        receipt = json.loads((directory / "native-result.json").read_text(encoding="utf-8"))
        assert receipt["caught"] == 0 and receipt["operation"] == operation
        return target

    _, _, meta, references = snapshot(sample)
    incoming = references["incoming"]["HALFADD"]
    assert sorted(row["reference"] for row in incoming) == ["halfadd_A", "halfadd_B"]
    assert not references["unresolved"]
    halfadd = next(row for row in meta["schematics"] if row["name"] == "HALFADD")
    assert halfadd["rawRefCount"] == 0
    try:
        require_unreferenced(references, "HALFADD")
    except CadenceError as error:
        assert error.code == "schematic_referenced"
    else:
        raise AssertionError("Referenced schematic was incorrectly accepted.")

    original = execute("create")
    auxiliary = execute("schematic_create", original)
    source_hash = sha256(auxiliary)
    names, pages, meta, references = snapshot(auxiliary)
    assert names == ["AUX", "ROOT"] and pages == [("AUX", "AUX_PAGE"), ("ROOT", "PAGE_ONE")]
    assert meta["rootName"] == "ROOT" and not references["unresolved"]
    assert not any(row["counts"][key] for row in meta["pages"] for key in row["counts"])
    require_unreferenced(references, "AUX")
    renamed = execute("schematic_rename", auxiliary)
    removed = execute("schematic_delete", auxiliary)
    names, pages, meta, refs = snapshot(renamed)
    assert names == ["AUX_RENAMED", "ROOT"] and pages == [("AUX_RENAMED", "AUX_PAGE"), ("ROOT", "PAGE_ONE")]
    assert meta["rootName"] == "ROOT" and refs == {"incoming": {"AUX_RENAMED": [], "ROOT": []}, "unresolved": []}
    names, pages, meta, refs = snapshot(removed)
    assert names == ["ROOT"] and pages == [("ROOT", "PAGE_ONE")]
    assert meta["rootName"] == "ROOT" and refs == {"incoming": {"ROOT": []}, "unresolved": []}
    assert sha256(auxiliary) == source_hash and sha256(sample) == before
    report = {"passed": True, "localIncomingReferences": len(incoming), "nativeRawRefCount": 0,
              "referencedGuardRejected": True, "privateUnreferencedCreateRenameDeleteReopened": True,
              "sourceUnchanged": True, "publicSchematicWriteAccepted": False}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "source", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    run(args.install_root, args.source, args.output)
