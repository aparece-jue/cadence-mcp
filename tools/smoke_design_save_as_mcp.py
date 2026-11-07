"""SPB 24.1 stdio acceptance of named, non-overwriting Save As."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json


async def run(install, source, output):
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "work"
    source_hash = sha256(source)
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(source.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    async def call(client, tool, args):
        reply = await client.call_tool(tool, args)
        assert not reply.is_error, (tool, reply.structured_content or reply.content)
        return reply.structured_content["data"]

    async def reject(client, tool, args, error):
        reply = await client.call_tool(tool, args)
        assert reply.is_error and reply.structured_content["error"]["code"] == error, (
            tool, reply.structured_content or reply.content)

    def key(plan):
        return {k: plan[k] for k in ("planId", "planDigest")}

    planner, applier = "capture_plan_design_save_as", "capture_apply_design_save_as"
    name = "Release Candidate 2.DSN"
    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        write_json(output / "tools-list.json", [tool.model_dump(mode="json", by_alias=True) for tool in tools])
        imported = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
        opened = await call(client, "capture_open", {"workspaceId": imported["workspaceId"]})
        arguments = {"sessionId": opened["sessionId"], "fileName": name}
        for unsafe in ("../foreign.dsn", "CON.data.dsn", "图纸.dsn"):
            await reject(client, planner, {**arguments, "fileName": unsafe}, "invalid_design_file_name")
        cancelled = key(await call(client, planner, arguments))
        assert (await call(client, "capture_cancel_design_save_as", cancelled))["state"] == "cancelled"
        await reject(client, applier, {**cancelled, "idempotencyKey": "cancelled"}, "write_not_replayed")
        collision = key(await call(client, planner, arguments))
        directory = workspace / "isolated-jobs/capture_design_save_as" / ("plan-" + collision["planId"])
        sentinel = directory / name
        sentinel.write_bytes(b"owned test collision sentinel")
        before = sha256(sentinel)
        await reject(client, applier, {**collision, "idempotencyKey": "collision"}, "output_exists")
        assert sha256(sentinel) == before and not (directory / "source-snapshot").exists()

        accepted = key(await call(client, planner, arguments))
        result = await call(client, applier, {**accepted, "idempotencyKey": "save-as"})
        assert result["sourceSnapshotUnchanged"] and result["effectiveInstancePropertiesVerified"]
        assert result["definitionDependenciesVerified"] and result["nativeRootAndPageCountsVerified"]
        assert result["connectionAndGraphicBaselineVerified"] and result["nativeCompletionVerified"]
        directory = workspace / result["outputWorkspaceRelativePath"]
        assert result["artifact"]["workspaceRelativePath"] == name
        saved = directory / name
        assert saved.is_file() and sha256(saved) == result["artifact"]["sha256"]
        assert sha256(directory / "source-snapshot/design.dsn") == source_hash
        assert sha256(workspace / imported["workspaceId"] / "design.dsn") == source_hash
        opened_copy = await call(client, "capture_open_edit_result", {**accepted, "kind": "design_save_as"})
        assert opened_copy["counts"] == opened["counts"]
        rows = await call(client, "capture_query", {"sessionId": opened_copy["sessionId"], "entity": "schematic",
                                                     "scope": {"kind": "design"}})
        owner, = [row for row in rows["items"] if row["name"] == "HALFADD"]
        chained = key(await call(client, "capture_plan_page_edit", {
            "sessionId": opened_copy["sessionId"], "operation": "create",
            "schematicId": owner["objectId"], "pageName": "SAVE_AS_CHAIN",
        }))
        chained_out = await call(client, "capture_apply_page_edit", {**chained, "idempotencyKey": "save-as-chain"})
        assert chained_out["independentReopenVerified"] and sha256(saved) == result["artifact"]["sha256"]

    # Simulate losing acknowledgement after the native worker completed and stopped.
    record = directory / "plan.json"
    row = json.loads(record.read_text(encoding="utf-8"))
    assert row["process"]["remainingOwnedProcesses"] == 0
    row["state"] = "started"
    row.pop("result")
    row.pop("verifiedAt")
    record.write_text(json.dumps(row), encoding="utf-8")
    (directory / "native-result.json").rename(directory / "saved-receipt.json")
    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        recovered = await call(client, "capture_recover_design_save_as", accepted)
        assert recovered["state"] == "verified_recovered" and recovered["nativeCompletionVerified"] is False
        assert recovered["artifact"]["sha256"] == sha256(saved) == result["artifact"]["sha256"]
        repeated = await call(client, applier, {**accepted, "idempotencyKey": "save-as"})
        assert repeated["mutationReplayed"] is False and not (directory / "native-result.json").exists()
        with saved.open("ab") as stream:
            stream.write(b"owned test corruption")
        await reject(client, applier, {**accepted, "idempotencyKey": "save-as"}, "target_changed")

    assert sha256(source) == source_hash
    report = {"passed": True, "tools": len(tools), "nativeNamedSaveAsReopened": True,
              "sourceBytesUnchanged": True, "effectivePropertiesAndDependenciesVerified": True,
              "unsafeBasenameCancellationAndCollisionRefused": True, "subsequentPageEditSucceeded": True,
              "verifyOnlyRecoveryAndTamperRefusal": True}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "source", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.output))
