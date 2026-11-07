"""Native SPB 24.1 MCP Unicode document round trips on the Windows code page."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json


async def run(install, output, sample):
    output.mkdir(parents=True, exist_ok=False)
    work = output / "work"
    source_hash = sha256(sample)
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(work),
        "--read-root", str(sample.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})

    async def call(client, tool, args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, (tool, result.structured_content or result.content)
        return result.structured_content["data"]

    async def refuse(client, tool, args, code):
        result = await client.call_tool(tool, args)
        assert result.is_error and result.structured_content["error"]["code"] == code, (
            tool, result.structured_content or result.content)

    async def rows(client, session, entity):
        query = {"sessionId": session, "entity": entity, "scope": {"kind": "design"}}
        return (await call(client, "capture_query", query))["items"]

    async def names(client, sid):
        schematics = {row["objectId"]: row["name"] for row in await rows(client, sid, "schematic")}
        pages = sorted((schematics[row["schematicId"]], row["name"]) for row in await rows(client, sid, "page"))
        return sorted(schematics.values()), pages

    async def select(client, sid, schematic_name, page_name=None):
        row, = [row for row in await rows(client, sid, "schematic") if row["name"] == schematic_name]
        result = {"sessionId": sid, "schematicId": row["objectId"]}
        if page_name is not None:
            page, = [item for item in await rows(client, sid, "page") if item["schematicId"] == row["objectId"]
                     and item["name"] == page_name]
            result["pageId"] = page["objectId"]
        return result

    checked = []
    async def apply(client, kind, inputs, label):
        plan = await call(client, "capture_plan_" + kind, inputs)
        key = {field: plan[field] for field in ("planId", "planDigest")}
        result = await call(client, "capture_apply_" + kind, {**key, "idempotencyKey": label})
        assert result["independentReopenVerified"] and result["nativeCompletionVerified"]
        path = work / result["outputWorkspaceRelativePath"] / result["artifact"]["workspaceRelativePath"]
        assert sha256(path) == result["artifact"]["sha256"]
        opened = await call(client, "capture_open_edit_result", {**key, "kind": kind})
        assert opened["revision"] == sha256(path)
        checked.append(label)
        return opened["sessionId"], path

    root_name, first_page = "电路", "原理图"
    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        write_json(output / "tools-list.json", [tool.model_dump(mode="json", by_alias=True) for tool in tools])
        sid, _ = await apply(client, "design_create", {"rootName": root_name, "pageName": first_page}, "create-unicode")
        assert await names(client, sid) == ([root_name], [(root_name, first_page)])
        await refuse(client, "capture_plan_page_edit", {
            **await select(client, sid, root_name), "operation": "create", "pageName": first_page,
        }, "page_name_conflict")
        sid, _ = await apply(client, "page_edit", {
            **await select(client, sid, root_name), "operation": "create", "pageName": "扩展页",
        }, "create-page")
        sid, _ = await apply(client, "page_edit", {
            **await select(client, sid, root_name, "扩展页"), "operation": "rename", "pageName": "修改页",
        }, "rename-page")
        assert set((await names(client, sid))[1]) == {
            (root_name, first_page), (root_name, "修改页")}
        sid, _ = await apply(client, "page_edit", {
            **await select(client, sid, root_name, "修改页"), "operation": "delete",
        }, "delete-page")
        sid, _ = await apply(client, "schematic_edit", {
            "sessionId": sid, "operation": "create", "schematicName": "接口", "pageName": "接口页",
        }, "create-schematic")
        sid, _ = await apply(client, "schematic_edit", {
            **await select(client, sid, "接口"), "operation": "rename", "schematicName": "控制",
        }, "rename-schematic")
        assert (await names(client, sid)) == (sorted([root_name, "控制"]), sorted([(root_name, first_page), ("控制", "接口页")]))
        sid, source = await apply(client, "schematic_edit", {
            **await select(client, sid, "控制"), "operation": "delete",
        }, "delete-schematic")
        before = sha256(source)
        sid, path = await apply(client, "design_save_as", {"sessionId": sid, "fileName": "设计副本.dsn"}, "save-as-unicode")
        assert path.name == "设计副本.dsn" and sha256(source) == before
        assert await names(client, sid) == ([root_name], [(root_name, first_page)])

        original = await call(client, "cadence_create_workspace", {"sourceDesign": str(sample)})
        sid = (await call(client, "capture_open", {"workspaceId": original["workspaceId"]}))["sessionId"]
        original_names = await names(client, sid)
        saved, path = await apply(client, "design_save_as", {"sessionId": sid, "fileName": "图纸校验.dsn"}, "save-as-titleblocks")
        assert path.name == "图纸校验.dsn" and await names(client, saved) == original_names
    assert sha256(sample) == source_hash
    report = {"passed": True, "tools": len(tools), "unicodeRootAndPageExact": True, "operations": checked,
              "unicodeNamedTitleblockDesignVerified": True, "sourceUnchanged": True}
    write_json(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "output", "sample"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.output, args.sample))
