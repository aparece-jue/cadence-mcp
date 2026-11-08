"""SPB 24.1 stdio acceptance of root-only, recursive and over-depth designs."""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import run_tcl


async def invoke(client, tool, args, expected_error=None):
    reply = await client.call_tool(tool, args)
    result = reply.structured_content
    if expected_error is None:
        assert not reply.is_error, (tool, result or reply.content)
    else:
        assert reply.is_error and result["error"]["code"] == expected_error, (tool, result)
        assert not result["evidence"]["complete"] and not result["data"]
    return result


def audit_definition_edges(config, source, label, output):
    path = output / f"{label}-definition-edges.json"
    run_tcl(config, "inspect_reference_units.tcl", [str(source), str(path), "contents"], output)
    rows = json.loads(path.read_text(encoding="utf-8"))
    root_targets = [row["contents"]["viewName"] for row in rows
                    if row["schematicName"] == "FULLADD" and row["reference"] == "halfadd_A"]
    if label == "cycle":
        assert root_targets == ["FULLADD"]
        return
    assert root_targets == ["DEPTH_001"]
    layers, branches = (65, 1) if label == "depth" else (15, 2)
    expected = Counter({(f"DEPTH_{i:03}", f"DEPTH_{i + 1:03}"): branches for i in range(1, layers)})
    actual = Counter((row["schematicName"], row["contents"]["viewName"])
                     for row in rows if row["schematicName"].startswith("DEPTH_"))
    assert actual == expected, (label, actual, expected)


async def run(install, empty, cycle, depth, fanout, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixtures = {"empty": empty, "cycle": cycle, "depth": depth, "fanout": fanout}
    files = {path: sha256(path) for path in fixtures.values()}
    workspace = output / "work"
    args = ["-B", "-m", "cadence_mcp.server", "--install-root", str(install),
            "--workspace-root", str(workspace), "--timeout-seconds", "60"]
    for source in files:
        args.extend(("--read-root", str(source.parent)))
    params = StdioServerParameters(command=sys.executable, args=args,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    report = {"passed": False, "fixtureSha256": {label: files[path] for label, path in fixtures.items()}}
    try:
        config = Config(install, workspace, tuple(path.parent for path in files), 60)
        for label in ("cycle", "depth", "fanout"):
            audit_definition_edges(config, fixtures[label], label, output)
        report["independentDefinitionEdgesMatch"] = True
        async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
            report["tools"] = len((await client.list_tools()).tools)
            for label, expected in (("empty", None), ("cycle", "hierarchy_cycle"),
                                    ("depth", "hierarchy_limit"), ("fanout", "hierarchy_limit")):
                source = fixtures[label]
                copied = (await invoke(client, "cadence_create_workspace", {"sourceDesign": str(source)}))["data"]
                opened = (await invoke(client, "capture_open", {"workspaceId": copied["workspaceId"]}))["data"]
                session = {"sessionId": opened["sessionId"]}
                first = await invoke(client, "capture_get_hierarchy", session, expected)
                if expected is None:
                    data = first["data"]
                    assert first["status"] == "partial" and not first["evidence"]["complete"]
                    assert not data["complete"] and not data["hierarchyComplete"] and data["incompleteReason"] == "empty_hierarchy"
                    assert data["total"] == 1 and data["nextCursor"] is None
                    root, = data["items"]
                    assert root["parentId"] is None and root["instancePathSegments"] == []
                    props = (await invoke(client, "capture_get_occurrence_properties", {
                        **session, "occurrenceId": root["occurrenceId"],
                    }))["data"]
                    assert props["context"] == "root_design_context" and props["definition"] is None
                    assert "Root View" in {row["name"] for row in props["effective"]}
                    report["emptyRootContextAndExplicitPartial"] = True
                else:
                    # A failed traversal cannot seed a cached tree for any subsequent call.
                    await invoke(client, "capture_get_hierarchy", session, expected)
                    await invoke(client, "capture_get_occurrence_properties", {
                        **session, "occurrenceId": "occ-1",
                    }, expected)
                    report[f"{label}ExplicitlyIncomplete"] = True
                assert sha256(workspace / copied["workspaceId"] / "design.dsn") == files[source]
                await invoke(client, "capture_close", session)
        report["passed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourcesUnchanged"] = all(sha256(path) == digest for path, digest in files.items())
        report["passed"] &= report["sourcesUnchanged"]
        write_json(output / "report.json", report)
        print(json.dumps(report), flush=True)
    assert report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "empty", "cycle", "depth", "fanout", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.empty, args.cycle, args.depth, args.fanout, args.output))
