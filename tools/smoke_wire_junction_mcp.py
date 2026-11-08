"""SPB 24.1 stdio acceptance for a fixed native PlaceJunction task."""
import argparse
import asyncio
from collections import defaultdict
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from audit_native_wire_partition import canonical_geometry, manual_groups
from smoke_wire_partition_mcp import call, key, open_page
from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import run_tcl
from cadence_mcp.gui_jobs import durable_json
from cadence_mcp.page_net_partition import page_partition


async def attach(client):
    instances = await call(client, "capture_gui_instances", {})
    instance, = instances["instances"]
    return (await call(client, "capture_gui_attach", {"instanceId": instance["instanceId"]}))["sessionId"]


async def run(install, source, host, bindings, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "work"
    source_hash = sha256(source)
    assert source_hash == "5d852a7683bb3d8b60d20a2505d856fa7c4adcd9d2de2f91b29dada242b926fe"
    hosts = {path: sha256(path) for path in [host, host.with_suffix(".dsn")]}
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(source.parent), "--read-root", str(host.parent),
        "--gui-bridge-root", str(bindings), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    report = {"passed": False}
    try:
        async with Client(params, mode="legacy", read_timeout_seconds=150) as client:
            tools = (await client.list_tools()).tools
            report["tools"] = len(tools)
            sid, page = await open_page(client, source, "MAIN")
            rows = (await call(client, "capture_query_connections", {
                "sessionId": sid, "entity": "wire", "pageId": page,
            }))["items"]
            h, = [row for row in rows if row["attributes"]["points"] == [[100, 350], [300, 350]]]
            v, = [row for row in rows if row["attributes"]["points"] == [[200, 300], [200, 400]]]
            gui = await attach(client)
            args = {"sessionId": sid, "pageId": page, "wireIds": [h["objectId"], v["objectId"]],
                    "location": [200, 350], "expectedConnections": [], "guiSessionId": gui,
                    "hostProject": str(host)}
            planner = "capture_plan_wire_junction"
            await call(client, planner, {**args, "location": [200, 351]}, "invalid_junction_crossing")
            await call(client, planner, {**args, "wireIds": [h["objectId"], "foreign"]}, "object_not_found")
            pending = key(await call(client, planner, args))
            await call(client, "capture_cancel_wire_edit", pending)
            await call(client, "capture_apply_wire_edit", {**pending, "idempotencyKey": "cancelled"}, "write_not_replayed")
            plan = await call(client, planner, args)
            assert len(plan["preview"]["expectedPageNetGroups"]) == 7
            request = key(plan)
            result = await call(client, "capture_apply_wire_edit", {**request, "idempotencyKey": "junction"})
            assert result["operation"] == "place_junction" and result["nativePageNetPartitionVerified"]
            assert result["hostContextPreserved"] and result["outputProjectCloseVerified"]
            artifact = workspace / result["outputWorkspaceRelativePath"] / result["artifact"]["workspaceRelativePath"]
            assert not artifact.with_suffix(".dsnlck").exists()
            reopened = await call(client, "capture_open_edit_result", {**request, "kind": "wire_edit"})
            assert reopened["revision"] == sha256(artifact)
            await call(client, "capture_close", {"sessionId": reopened["sessionId"]})
            report["nativeEditorSaveReopenAndHostRestored"] = True

        independent = output / "native-output.json"
        config = Config(install, workspace, (source.parent, host.parent), 60)
        run_tcl(config, "inspect_page_net_partition.tcl", [str(artifact), str(independent)], output)
        rows = json.loads(independent.read_text(encoding="utf-8"))
        page_partition(rows)
        groups = defaultdict(list)
        for row in rows:
            assert row["kind"] == "wire" and (row["schematicName"], row["pageName"]) == ("ROOT", "MAIN")
            groups[row["group"]].append(row["points"])
        assert canonical_geometry(groups.values()) == canonical_geometry(manual_groups(True))
        report["manualAllSevenNodesMatch"] = True
        # Simulate losing the final verification journal update after the worker stopped.
        record = artifact.parent / "plan.json"
        journal = json.loads(record.read_text(encoding="utf-8"))
        assert journal["state"] == "verified" and journal["process"]["remainingOwnedProcesses"] == 0
        journal["state"] = "started"
        journal.pop("result")
        journal.pop("verifiedAt")
        durable_json(record, journal)
        async with Client(params, mode="legacy", read_timeout_seconds=150) as fresh:
            verified = await call(fresh, "capture_recover_wire_edit", request)
            assert verified["state"] == "verified_recovered" and not verified["nativeCompletionVerified"]
            assert verified["nativePageNetPartitionVerified"] and not verified["mutationReplayed"]
            replay = await call(fresh, "capture_apply_wire_edit", {**request, "idempotencyKey": "junction"})
            assert not replay["mutationReplayed"] and sha256(artifact) == reopened["revision"]
        report.update(passed=True, verifyOnlyRecoveryAfterJournalLoss=True,
                      freshServiceNoReplay=True, invalidAndCancelledRefused=True)
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourceAndHostUnchanged"] = sha256(source) == source_hash and all(
            sha256(path) == value for path, value in hosts.items())
        report["passed"] = report["passed"] and report["sourceAndHostUnchanged"]
        write_json(output / "report.json", report)
        print(json.dumps(report), flush=True)
    assert report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "source", "host", "bindings", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.host, args.bindings, args.output))
