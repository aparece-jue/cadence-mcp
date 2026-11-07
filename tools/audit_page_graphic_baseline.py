"""Locate the graphic-baseline mismatch in the original E04 fixture jobs."""
import argparse
from collections import Counter
import json
from pathlib import Path

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_objects import query_objects
from cadence_mcp.core import Config, sha256, write_json


def snapshot(capture, path, rename=None):
    workspace = capture.create_workspace(str(path))
    sid = capture.open(workspace["workspaceId"])["sessionId"]
    try:
        session = capture._session(sid)
        query_objects(capture, sid, "graphics", "graphic", None, None, 1)
        data = session["data"]
        schematics = {row["objectId"]: row["name"] for row in data["schematic"]}
        parts = {row["objectId"]: row["reference"] for row in data["part"]}
        pages = {row["objectId"]: (schematics[row["schematicId"]], row["name"]) for row in data["page"]}
        if rename:
            old, new = rename
            pages = {key: new if value == old else value for key, value in pages.items()}
        graphics = Counter()
        titleblocks = {}
        for row in session["objectInventories"]["graphics"]:
            attributes = dict(row["attributes"])
            owner = attributes.pop("partId", None)
            if owner is not None:
                attributes["ownerReference"] = parts[owner]
            page = pages[row["pageId"]]
            if row["kind"] == "titleblock":
                key = (*page, row["nativeId"])
                assert key not in titleblocks
                titleblocks[key] = attributes
            else:
                # Display item native IDs can change even when their semantics
                # are stable. Keep duplicates by comparing a multiset.
                graphics[(row["kind"], page, json.dumps(attributes, sort_keys=True))] += 1
        return graphics, titleblocks
    finally:
        capture.close(sid)


def audit(install, old, output):
    original_report = old / "report.json"
    before_report = sha256(original_report)
    baseline = json.loads(original_report.read_text(encoding="utf-8"))
    source, = (old / "work").glob("ws-*/design.dsn")
    assert sha256(source) == baseline["sourceHashBefore"] == baseline["sourceHashAfter"]
    assert baseline["passed"] is False
    output.mkdir(parents=True, exist_ok=False)
    capture = CaptureService(Config(install, output / "work", (old,), 60))
    result = {}
    for plan in sorted((old / "work/isolated-jobs/capture_page").glob("plan-*/plan.json")):
        plan_hash = sha256(plan)
        record = json.loads(plan.read_text(encoding="utf-8"))
        assert record["state"] == "failed" and record["error"]["code"] == "page_graphic_mismatch"
        payload = record["plan"]["payload"]
        operation = payload["operation"]
        renamed = None
        if operation == "rename":
            schematic = payload["schematicName"]
            renamed = ((schematic, payload["oldName"]), (schematic, payload["name"]))
        target = plan.parent / "design.dsn"
        target_hash = sha256(target)
        before, old_titles = snapshot(capture, source, renamed)
        after, new_titles = snapshot(capture, target)
        assert before == after and old_titles.keys() == new_titles.keys()
        fields = set()
        for key in old_titles:
            original = dict(old_titles[key])
            saved = dict(new_titles[key])
            old_properties = {row["name"]: row["value"] for row in original.pop("properties")}
            new_properties = {row["name"]: row["value"] for row in saved.pop("properties")}
            assert original == saved
            fields.update(name for name in old_properties.keys() | new_properties.keys()
                          if old_properties.get(name) != new_properties.get(name))
        assert fields and sha256(target) == target_hash and sha256(plan) == plan_hash
        result[operation] = {"graphicRowsExact": sum(before.values()), "titleblocks": len(old_titles),
                             "changedTitleblockPropertyNames": sorted(fields)}
    assert set(result) == {"create", "rename"}
    assert sha256(source) == baseline["sourceHashBefore"] and sha256(original_report) == before_report
    report = {"diagnosticComplete": True, "originalFailurePreserved": True, "cases": result}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "original-job-root", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    audit(args.install_root, args.original_job_root, args.output)
