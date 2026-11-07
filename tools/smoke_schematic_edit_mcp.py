"""Real SPB 24.1 MCP schematic lifecycle and refusal cases."""
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
    work = output / "work"
    source_hash = sha256(source)
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(work),
        "--read-root", str(source.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    async def call(client, name, inputs):
        result = await client.call_tool(name, inputs)
        assert not result.is_error, (name, result.structured_content or result.content)
        return result.structured_content["data"]

    async def reject(client, name, inputs, code):
        result = await client.call_tool(name, inputs)
        assert result.is_error and result.structured_content["error"]["code"] == code, (
            name, result.structured_content or result.content)

    async def rows(client, sid, entity):
        return (await call(client, "capture_query",
                           {"sessionId": sid, "entity": entity, "scope": {"kind": "design"}}))["items"]

    async def schematic(client, sid, name):
        row, = [row for row in await rows(client, sid, "schematic") if row["name"] == name]
        return {"sessionId": sid, "schematicId": row["objectId"]}

    async def open_result(client, key, kind="schematic_edit"):
        return (await call(client, "capture_open_edit_result", {**key, "kind": kind}))["sessionId"]

    def key(plan):
        return {field: plan[field] for field in ("planId", "planDigest")}

    planner = "capture_plan_schematic_edit"
    applier = "capture_apply_schematic_edit"
    jobs = []

    async def apply(client, inputs):
        label = inputs["operation"]
        plan = key(await call(client, planner, inputs))
        result = await call(client, applier, {**plan, "idempotencyKey": label})
        assert result["independentReopenVerified"] and result["definitionDependenciesVerified"]
        assert result["connectionAndGraphicBaselineVerified"] and result["nativeRootAndPageCountsVerified"]
        directory = work / result["outputWorkspaceRelativePath"]
        record = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
        assert record["process"]["remainingOwnedProcesses"] == 0
        assert sha256(directory / "design.dsn") == result["artifact"]["sha256"]
        jobs.append((label, plan, result["artifact"], directory))
        return await open_result(client, plan)

    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        write_json(output / "tools-list.json", [tool.model_dump(mode="json", by_alias=True) for tool in tools])
        workspace = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
        sid = (await call(client, "capture_open", {"workspaceId": workspace["workspaceId"]}))["sessionId"]
        before = sorted(row["name"] for row in await rows(client, sid, "schematic"))
        assert before == ["FULLADD", "HALFADD"]
        root = await schematic(client, sid, "FULLADD")
        referenced = await schematic(client, sid, "HALFADD")
        for operation in ("rename", "delete"):
            extra = {"schematicName": "NEW_NAME"} if operation == "rename" else {}
            await reject(client, planner, {**root, "operation": operation, **extra}, "root_schematic_protected")
            await reject(client, planner, {**referenced, "operation": operation, **extra}, "schematic_referenced")
        create = {"sessionId": sid, "operation": "create", "schematicName": "AUX", "pageName": "AUX_PAGE"}
        await reject(client, planner, {**create, "schematicName": "fulladd"}, "schematic_name_conflict")
        await reject(client, planner, {**create, "schematicName": "电路/错误"}, "invalid_document_name")
        cancelled = key(await call(client, planner, create))
        assert (await call(client, "capture_cancel_schematic_edit", cancelled))["state"] == "cancelled"
        await reject(client, applier, {**cancelled, "idempotencyKey": "cancelled"}, "write_not_replayed")
        sid = await apply(client, create)
        aux = await schematic(client, sid, "AUX")
        page, = [row for row in await rows(client, sid, "page") if row["schematicId"] == aux["schematicId"]]
        assert page["name"] == "AUX_PAGE"
        line = key(await call(client, "capture_plan_graphic_line_add", {
            "sessionId": sid, "pageId": page["objectId"], "start": [100, 100], "end": [300, 100],
        }))
        await call(client, "capture_apply_graphic_line_add", {**line, "idempotencyKey": "populate-aux"})
        filled = await schematic(client, await open_result(client, line, "graphic_line"), "AUX")
        for operation in ("rename", "delete"):
            extra = {"schematicName": "NEW_NAME"} if operation == "rename" else {}
            await reject(client, planner, {**filled, "operation": operation, **extra}, "schematic_not_empty")
        sid = await apply(client, {**aux, "operation": "rename", "schematicName": "AUX_RENAMED"})
        sid = await apply(client, {**await schematic(client, sid, "AUX_RENAMED"), "operation": "delete"})
        assert sorted(row["name"] for row in await rows(client, sid, "schematic")) == before

    # Model loss of the final acknowledgement using only the saved test job.
    _, deletion, artifact, directory = jobs[-1]
    plan_file = directory / "plan.json"
    interrupted = json.loads(plan_file.read_text(encoding="utf-8"))
    interrupted["state"] = "started"
    interrupted.pop("result")
    interrupted.pop("verifiedAt")
    plan_file.write_text(json.dumps(interrupted), encoding="utf-8")
    (directory / "native-result.json").rename(directory / "saved-receipt.json")

    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        result = await call(client, "capture_recover_schematic_edit", deletion)
        assert result["state"] == "verified_recovered" and result["nativeCompletionVerified"] is False
        assert result["artifact"]["sha256"] == artifact["sha256"] == sha256(directory / "design.dsn")
        assert not (directory / "native-result.json").exists()
        for label, plan, original, _ in jobs:
            result = await call(client, applier, {**plan, "idempotencyKey": label})
            assert result["artifact"]["sha256"] == original["sha256"] and result["mutationReplayed"] is False
    assert sha256(source) == source_hash
    report = {"passed": True, "tools": len(tools), "operations": [row[0] for row in jobs],
              "rootReferencedPopulatedRefused": True, "duplicateInvalidNameAndCancelledRefused": True,
              "restartNoReplayAndVerifyOnlyRecovery": True, "sourceUnchanged": True}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "source", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.output))
