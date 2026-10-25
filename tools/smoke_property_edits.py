"""Actual stdio plan/apply/restart acceptance on an official sample copy."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256


async def main(args):
    args.workspace_root.mkdir(parents=True, exist_ok=False)
    before = sha256(args.source)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "cadence_mcp.server",
        "--install-root", str(args.install_root), "--workspace-root", str(args.workspace_root / "work"),
        "--read-root", str(args.source.parent), "--timeout-seconds", "60"], env=env)
    report = {"featureId": "E01", "createdAt": datetime.now(timezone.utc).isoformat(),
              "passed": False, "sourceHashBefore": before, "transport": "stdio", "checks": {}, "cases": []}
    try:
        async with Client(params, mode="legacy", read_timeout_seconds=90) as client:
            tools = (await client.list_tools()).tools
            schemas = {tool.name: tool.output_schema for tool in tools}
            for tool in tools:
                Draft202012Validator.check_schema(tool.input_schema)
                Draft202012Validator.check_schema(tool.output_schema)
            (args.workspace_root / "tools-list.json").write_text(json.dumps([
                tool.model_dump(mode="json", by_alias=True) for tool in tools], ensure_ascii=False, indent=2), encoding="utf-8")
            async def call(name, values):
                result = await client.call_tool(name, values)
                assert not result.is_error, result.structured_content or result.content
                Draft202012Validator(schemas[name]).validate(result.structured_content)
                return result.structured_content["data"]
            ws = await call("cadence_create_workspace", {"sourceDesign": str(args.source)})
            opened = await call("capture_open", {"workspaceId": ws["workspaceId"]})
            sid = opened["sessionId"]
            async def query(entity):
                return (await call("capture_query", {"sessionId": sid, "entity": entity, "scope": {"kind": "design"}, "limit": 1000}))["items"]
            schematics = {row["objectId"]: row["name"] for row in await query("schematic")}
            pages = {row["objectId"]: row["name"] for row in await query("page")}
            parts = await query("part")
            selected = [row for row in parts if schematics[row["schematicId"]] == "FULLADD"
                        and pages[row["pageId"]] == "FULLADD" and row["reference"] == "U1"]
            assert len(selected) == 1
            part_id = selected[0]["objectId"]
            forbidden = await client.call_tool("capture_plan_property", {"sessionId": sid, "partId": part_id,
                                                  "propertyName": "Implementation", "value": "forbidden"})
            assert forbidden.is_error
            report["checks"]["unapproved_field_rejected"] = True
            counts = Counter((row["pageId"], row["reference"]) for row in parts)
            duplicate = next((row for row in parts if counts[(row["pageId"], row["reference"])] > 1), None)
            if duplicate is not None:
                rejected = await client.call_tool("capture_plan_property", {"sessionId": sid, "partId": duplicate["objectId"],
                                                      "propertyName": "PCB Footprint", "value": "not_written"})
                assert rejected.is_error and rejected.structured_content["error"]["code"] == "ambiguous_target"
                report["checks"]["shared_reference_rejected"] = True
            pending = await call("capture_plan_property", {"sessionId": sid, "partId": part_id,
                                    "propertyName": "PCB Footprint", "value": "PENDING_CANCEL_TEST"})
            await call("capture_cancel_property", {"planId": pending["planId"], "planDigest": pending["planDigest"]})
            cancelled = await client.call_tool("capture_apply_property", {"planId": pending["planId"], "planDigest": pending["planDigest"], "idempotencyKey": "cancelled-key"})
            assert cancelled.is_error and cancelled.structured_content["error"]["code"] == "write_not_replayed"
            report["checks"]["pending_cancel_never_applied"] = True
            cases = [("PCB Footprint", "MCP_FP_STDIO_TEST"), ("Value", "MCP_VALUE_STDIO_TEST"),
                     ("PCB Footprint", 'MCP_封装_[x]{$};"\\\nEND')]
            for index, (field, value) in enumerate(cases):
                plan = await call("capture_plan_property", {"sessionId": sid, "partId": part_id, "propertyName": field, "value": value})
                assert plan["preview"]["value"] == value and not plan["sourceWillBeModified"]
                key = f"stdio-property-{index}"
                result = await call("capture_apply_property", {"planId": plan["planId"], "planDigest": plan["planDigest"], "idempotencyKey": key})
                assert result["expectedValue"] == result["observedValue"] == value
                assert result["independentReopenVerified"] and result["definitionBaselinePreserved"]
                assert result["nativeCompletionVerified"] and not result["electricalBehaviorVerified"]
                assert result["designPassed"] is None and not result["sourceModified"]
                folder = args.workspace_root / "work" / result["outputWorkspaceRelativePath"]
                assert sha256(folder / "design.dsn") == result["artifact"]["sha256"]
                report["cases"].append({"plan": plan, "key": key, "result": result, "planRecordSha256": sha256(folder / "plan.json")})
            report["checks"]["both_fields_and_unicode_literal_save_reopen"] = True
            listing = await client.call_tool("capture_property_jobs", {"offset": 0, "limit": 1})
            assert listing.structured_content["status"] == "partial" and not listing.structured_content["evidence"]["complete"]
            report["checks"]["durable_jobs_pagination"] = True
            await call("capture_close", {"sessionId": sid})
            assert sha256(args.workspace_root / "work" / ws["workspaceId"] / "design.dsn") == before
            report["checks"]["input_workspace_unchanged"] = True
        async with Client(params, mode="legacy", read_timeout_seconds=90) as fresh:
            for case in report["cases"]:
                plan = case["plan"]
                repeated = await fresh.call_tool("capture_apply_property", {"planId": plan["planId"], "planDigest": plan["planDigest"], "idempotencyKey": case["key"]})
                assert not repeated.is_error and repeated.structured_content["data"] == case["result"]
                folder = args.workspace_root / "work" / case["result"]["outputWorkspaceRelativePath"]
                assert sha256(folder / "plan.json") == case["planRecordSha256"]
            report["checks"]["fresh_stdio_server_idempotence_without_journal_change"] = True
        report["sourceHashAfter"] = sha256(args.source)
        assert before == report["sourceHashAfter"]
        report["checks"]["source_unchanged"] = True
        report["passed"] = True
    except Exception as error:
        report["errorType"] = type(error).__name__
        raise
    finally:
        (args.workspace_root / "property-edits-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.workspace_root / "property-edits-report.json"), "passed": report["passed"],
                      "toolCount": len(tools), "cases": len(report["cases"]), "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--install-root", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--workspace-root", required=True, type=Path)
    asyncio.run(main(p.parse_args()))
