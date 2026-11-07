"""SPB 24.1 stdio MCP acceptance for isolated page edits on a FULLADD sample."""
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
    source_hash = sha256(source)
    workspace = output / "work"
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(source.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    async def call(client, name, args):
        reply = await client.call_tool(name, args)
        assert not reply.is_error, (name, reply.structured_content or reply.content)
        return reply.structured_content["data"]

    async def reject(client, name, args, code):
        reply = await client.call_tool(name, args)
        assert reply.is_error and reply.structured_content["error"]["code"] == code, (name, reply.structured_content or reply.content)

    async def list_rows(client, sid, kind):
        return (await call(client, "capture_query", {"sessionId": sid, "entity": kind, "scope": {"kind": "design"}}))["items"]

    async def locate(client, sid, page=None):
        schematic, = [row for row in await list_rows(client, sid, "schematic") if row["name"] == "HALFADD"]
        args = {"sessionId": sid, "schematicId": schematic["objectId"]}
        if page:
            match, = [row for row in await list_rows(client, sid, "page")
                      if row["schematicId"] == schematic["objectId"] and row["name"] == page]
            args["pageId"] = match["objectId"]
        return args

    plans = []

    async def apply(client, args, label):
        plan = await call(client, "capture_plan_page_edit", args)
        key = {field: plan[field] for field in ("planId", "planDigest")}
        result = await call(client, "capture_apply_page_edit", {**key, "idempotencyKey": label})
        assert result["nativeCompletionVerified"] and result["independentReopenVerified"]
        assert result["connectionAndGraphicBaselineVerified"] and result["nativeRootAndPageCountsVerified"]
        directory = workspace / result["outputWorkspaceRelativePath"]
        job = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
        assert job["process"]["remainingOwnedProcesses"] == 0
        assert sha256(directory / "design.dsn") == result["artifact"]["sha256"]
        plans.append((label, key, result["artifact"]))
        opened = await call(client, "capture_open_edit_result", {**key, "kind": "page_edit"})
        return opened["sessionId"]

    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        assert any(tool.name == "capture_plan_page_edit" for tool in tools)
        write_json(output / "tools-list.json", [tool.model_dump(mode="json", by_alias=True) for tool in tools])
        entry = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
        sid = (await call(client, "capture_open", {"workspaceId": entry["workspaceId"]}))["sessionId"]
        original_pages = [(row["name"], row["schematicId"]) for row in await list_rows(client, sid, "page")]
        planner = "capture_plan_page_edit"
        await reject(client, planner, {**await locate(client, sid, "HALFADD"), "operation": "delete"}, "last_page")
        await reject(client, planner, {**await locate(client, sid), "operation": "create", "pageName": "halfadd"}, "page_name_conflict")
        await reject(client, planner, {**await locate(client, sid), "operation": "create", "pageName": "温度/错误"}, "invalid_page_change")
        new = {**await locate(client, sid), "operation": "create", "pageName": "MCP_EMPTY_ACCEPT"}
        cancelled = await call(client, planner, new)
        cancel_key = {field: cancelled[field] for field in ("planId", "planDigest")}
        assert (await call(client, "capture_cancel_page_edit", cancel_key))["state"] == "cancelled"
        await reject(client, "capture_apply_page_edit", {**cancel_key, "idempotencyKey": "cancelled"}, "write_not_replayed")
        sid = await apply(client, new, "create")
        await reject(client, planner, {**await locate(client, sid, "HALFADD"), "operation": "delete"}, "page_not_empty")
        sid = await apply(client, {**await locate(client, sid, "MCP_EMPTY_ACCEPT"), "operation": "rename",
                                   "pageName": "MCP_EMPTY_RENAMED"}, "rename-empty")
        sid = await apply(client, {**await locate(client, sid, "HALFADD"), "operation": "rename",
                                   "pageName": "MCP_RENAMED_ACCEPT"}, "rename-populated")
        sid = await apply(client, {**await locate(client, sid, "MCP_EMPTY_RENAMED"), "operation": "delete"}, "delete-empty")
        final_pages = [(row["name"], row["schematicId"]) for row in await list_rows(client, sid, "page")]
        assert sorted(final_pages) == sorted(("MCP_RENAMED_ACCEPT" if name == "HALFADD" else name, scope)
                                             for name, scope in original_pages)

    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        for label, key, artifact in plans:
            replay = await call(client, "capture_apply_page_edit", {**key, "idempotencyKey": label})
            assert replay["artifact"] == artifact and replay["mutationReplayed"] is False
    assert sha256(source) == source_hash
    report = {"passed": True, "operations": [label for label, _, _ in plans], "sourceUnchanged": True,
              "lastPageAndPopulatedDeleteRefused": True, "duplicateAndInvalidNameRefused": True,
              "pendingCancelAndRestartIdempotence": True, "tools": len(tools)}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "source", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.output))
