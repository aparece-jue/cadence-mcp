"""Verify explicit native wire and pin groups through real MCP write workflows."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json


MOVED_GROUPS = [
    [[[100, 120], [300, 120]]],
    [[[100, 200], [200, 200]], [[200, 200], [200, 250]]],
    [[[100, 350], [200, 350]], [[200, 300], [200, 350]],
     [[200, 350], [200, 400]], [[200, 350], [300, 350]]],
    [[[400, 100], [500, 100]], [[500, 100], [500, 200]], [[500, 100], [600, 100]]],
    [[[400, 300], [700, 300]]],
    [[[400, 500], [450, 500]]],
    [[[460, 500], [550, 500]]],
]


async def call(client, tool, args, expected_error=None):
    reply = await client.call_tool(tool, args)
    content = reply.structured_content
    if expected_error:
        assert reply.is_error and content["error"]["code"] == expected_error, (tool, content)
        return None
    assert not reply.is_error, (tool, content or reply.content)
    return content["data"]


def key(plan):
    return {name: plan[name] for name in ("planId", "planDigest")}


async def open_page(client, source, page_name):
    ws = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
    session = (await call(client, "capture_open", {"workspaceId": ws["workspaceId"]}))["sessionId"]
    pages = await call(client, "capture_query", {"sessionId": session, "entity": "page", "scope": {"kind": "design"}})
    page, = [row for row in pages["items"] if row["name"] == page_name]
    return session, page["objectId"]


def declare_groups(wire_groups):
    paths, groups = [], []
    for group in wire_groups:
        groups.append({"wireIndexes": list(range(len(paths), len(paths) + len(group))), "pinIndexes": []})
        paths.extend(group)
    return {"expectedWirePaths": paths, "expectedPageNetGroups": groups}


async def run(install, resistor, junction, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = {resistor: "799f57bd53626a19c8fbb006523e3844d5c1ddd52856f31cf0c920cd9fc50b22",
              junction: "8184f7f92848f536e9bc7a7969b5b597fe62515b1dfe5fef1bcb814b5e599397"}
    assert all(sha256(source) == expected for source, expected in inputs.items())
    workspace = output / "work"
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(resistor.parent), "--read-root", str(junction.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    report = {"passed": False}
    try:
        async with Client(params, mode="legacy", read_timeout_seconds=150) as client:
            report["tools"] = len((await client.list_tools()).tools)
            session, page = await open_page(client, resistor, "MCP_PLACE")
            expected_pins = []
            for ref, number in (("R101", "1"), ("R101", "2"), ("R102", "1"), ("R102", "2")):
                connected = (ref, number) in (("R101", "2"), ("R102", "1"))
                expected_pins.append({"schematicName": "HALFADD", "pageName": "MCP_PLACE", "reference": ref,
                                      "pinNumber": number, "connected": connected,
                                      "net": "MCP_MIDDLE" if connected else None})
            add_args = {"sessionId": session, "pageId": page, "start": [330, 310], "end": [490, 310],
                        "netName": "MCP_MIDDLE", "expectedConnections": expected_pins,
                        "expectedWirePaths": [[[330, 310], [490, 310]]],
                        "expectedPageNetGroups": [{"wireIndexes": [0], "pinIndexes": [1, 2]}]}
            await call(client, "capture_plan_wire_add", {
                **add_args, "expectedPageNetGroups": [{"wireIndexes": [0], "pinIndexes": [1]}],
            }, "incomplete_page_net_groups")
            added = key(await call(client, "capture_plan_wire_add", add_args))
            add_result = await call(client, "capture_apply_wire_add", {**added, "idempotencyKey": "pin-groups"})
            assert add_result["nativePageNetPartitionVerified"] and add_result["independentReopenVerified"]
            report["resistorWireAndTwoPinsVerified"] = True
            opened = await call(client, "capture_open_edit_result", {**added, "kind": "wire_add"})
            sid = opened["sessionId"]
            pages = await call(client, "capture_query", {"sessionId": sid, "entity": "page", "scope": {"kind": "design"}})
            saved_page, = [row for row in pages["items"] if row["name"] == "MCP_PLACE"]
            wire, = (await call(client, "capture_query_connections", {"sessionId": sid, "entity": "wire",
                            "pageId": saved_page["objectId"]}))["items"]
            removed = key(await call(client, "capture_plan_wire_edit", {
                "sessionId": sid, "wireId": wire["objectId"], "operation": "delete",
                "removeAttachedAliases": True, "expectedWirePaths": [], "expectedPageNetGroups": [],
                "expectedConnections": [{**pin, "connected": False, "net": None} for pin in expected_pins],
            }))
            removed_result = await call(client, "capture_apply_wire_edit", {**removed, "idempotencyKey": "zero-groups"})
            assert removed_result["nativePageNetPartitionVerified"]
            report["wireDeletedAndFourPinsUnbound"] = True

            session, page = await open_page(client, junction, "MAIN")
            wires = (await call(client, "capture_query_connections", {
                "sessionId": session, "entity": "wire", "pageId": page,
            }))["items"]
            target, = [row for row in wires if row["attributes"]["points"] == [[100, 100], [300, 100]]]
            expected = declare_groups(MOVED_GROUPS)
            groups = expected["expectedPageNetGroups"]
            edit_args = {"sessionId": session, "wireId": target["objectId"], "operation": "set_endpoints",
                         "start": [100, 120], "end": [300, 120], "expectedWireNet": "N00001",
                         "expectedConnections": [], **expected}
            edited = key(await call(client, "capture_plan_wire_edit", edit_args))
            edit_result = await call(client, "capture_apply_wire_edit", {**edited, "idempotencyKey": "move-exact-groups"})
            assert edit_result["nativePageNetPartitionVerified"]
            report["endpointEditAllSevenNodesVerified"] = True
            bad = key(await call(client, "capture_plan_wire_edit", {
                **edit_args, "expectedPageNetGroups": groups[:-2] + [
                    {"wireIndexes": groups[-2]["wireIndexes"] + groups[-1]["wireIndexes"], "pinIndexes": []},
                ],
            }))
            await call(client, "capture_apply_wire_edit", {**bad, "idempotencyKey": "false-gap-merge"}, "wire_page_partition_mismatch")
            await call(client, "capture_open_edit_result", {**bad, "kind": "wire_edit"}, "output_unverified")
            await call(client, "capture_apply_wire_edit", {**bad, "idempotencyKey": "false-gap-merge"}, "write_not_replayed")
            report["falseGapMergeRejectedAfterNativeSave"] = True

            arm, = [row for row in wires if row["attributes"]["points"] == [[100, 350], [200, 350]]]
            remaining = [[[[100, 100], [300, 100]]], MOVED_GROUPS[1], MOVED_GROUPS[2][1:], *MOVED_GROUPS[3:]]
            branch_removed = key(await call(client, "capture_plan_wire_edit", {
                "sessionId": session, "wireId": arm["objectId"], "operation": "delete", "expectedConnections": [],
                **declare_groups(remaining),
            }))
            branch_result = await call(client, "capture_apply_wire_edit", {**branch_removed, "idempotencyKey": "branch-delete"})
            assert branch_result["nativePageNetPartitionVerified"]
            report["connectedJunctionBranchDeletePreservedRemainingNodes"] = True
        async with Client(params, mode="legacy", read_timeout_seconds=150) as fresh:
            for prefix, plan in (("wire_add", added), ("wire_edit", removed), ("wire_edit", edited), ("wire_edit", branch_removed)):
                result = await call(fresh, f"capture_recover_{prefix}", plan)
                assert result["nativePageNetPartitionVerified"] and not result["mutationReplayed"]
            report["freshServiceDoesNotReplayVerifiedPlans"] = True
        report["passed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourcesUnchanged"] = all(sha256(source) == expected for source, expected in inputs.items())
        report["passed"] = report["passed"] and report["sourcesUnchanged"]
        write_json(output / "report.json", report)
        print(json.dumps(report), flush=True)
    assert report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "resistor", "junction", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.resistor, args.junction, args.output))
