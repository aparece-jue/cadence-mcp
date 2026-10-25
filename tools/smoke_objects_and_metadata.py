"""Native stdio objects plus explicit metadata lifecycle and output chaining."""
import argparse
import asyncio
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
    params = StdioServerParameters(command=sys.executable, args=["-m", "cadence_mcp.server", "--install-root", str(args.install_root),
        "--workspace-root", str(args.workspace_root / "work"), "--read-root", str(args.source.parent), "--timeout-seconds", "60"], env=env)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "passed": False, "checks": {}, "sourceHashBefore": before, "cases": []}
    try:
        async with Client(params, mode="legacy", read_timeout_seconds=90) as client:
            tools = (await client.list_tools()).tools
            schemas = {tool.name: tool.output_schema for tool in tools}
            for tool in tools:
                Draft202012Validator.check_schema(tool.input_schema)
                Draft202012Validator.check_schema(tool.output_schema)
            (args.workspace_root / "tools-list.json").write_text(json.dumps([tool.model_dump(mode="json", by_alias=True) for tool in tools], ensure_ascii=False, indent=2), encoding="utf-8")
            async def call(name, values):
                result = await client.call_tool(name, values)
                assert not result.is_error, result.structured_content or result.content
                Draft202012Validator(schemas[name]).validate(result.structured_content)
                return result.structured_content["data"]
            ws = await call("cadence_create_workspace", {"sourceDesign": str(args.source)})
            opened = await call("capture_open", {"workspaceId": ws["workspaceId"]})
            current = opened
            counts = {}
            for tool, entities in (("capture_query_connections", ("wire", "alias", "global", "port", "offpage", "nc")),
                                   ("capture_query_graphics", ("part_bounds", "display_property", "graphic", "titleblock"))):
                for entity in entities:
                    rows, cursor = [], None
                    while True:
                        page = await call(tool, {"sessionId": current["sessionId"], "entity": entity, "limit": 3, "cursor": cursor})
                        assert page["revision"] == current["revision"] and not page["electricalConnectivityVerified"]
                        rows.extend(page["items"])
                        cursor = page["nextCursor"]
                        if cursor is None:
                            break
                    assert len(rows) == page["total"]
                    counts[entity] = len(rows)
            assert counts["wire"] == 28 and counts["alias"] == 1 and counts["port"] == 9
            assert counts["part_bounds"] == 9 and counts["display_property"] == 18 and counts["titleblock"] == 2
            report["objectCounts"] = counts
            report["checks"]["all_object_entities_pagination_and_empty_categories"] = True

            async def selected_part(session):
                result = {}
                for entity in ("schematic", "page", "part"):
                    result[entity] = (await call("capture_query", {"sessionId": session["sessionId"], "entity": entity, "scope": {"kind": "design"}, "limit": 1000}))["items"]
                names = {row["objectId"]: row["name"] for row in result["schematic"]}
                pages = {row["objectId"]: row["name"] for row in result["page"]}
                matches = [row for row in result["part"] if names[row["schematicId"]] == "FULLADD" and pages[row["pageId"]] == "FULLADD" and row["reference"] == "U1"]
                assert len(matches) == 1
                return matches[0]["objectId"]

            for index, (operation, value) in enumerate((("set", '料号_[]{$};"\\\nA'), ("set", ""), ("delete", None))):
                part_id = await selected_part(current)
                plan = await call("capture_plan_user_property", {"sessionId": current["sessionId"], "partId": part_id,
                    "operation": operation, "propertyName": "MCP_MPN", "value": value, "expectedEffectiveAfterDelete": None})
                key = f"metadata-stdio-{index}"
                result = await call("capture_apply_user_property", {"planId": plan["planId"], "planDigest": plan["planDigest"], "idempotencyKey": key})
                assert result["userPropertyExists"] == (operation == "set")
                assert result["observedEffectiveValue"] == value
                assert result["unrelatedUserPropertiesPreserved"] and result["definitionBaselinePreserved"]
                next_session = await call("capture_open_edit_result", {"planId": plan["planId"], "planDigest": plan["planDigest"], "kind": "user_property"})
                next_part = await selected_part(next_session)
                layers = await call("capture_get_property_layers", {"sessionId": next_session["sessionId"], "partId": next_part})
                users = {row["name"]: row["value"] for row in layers["user"]}
                assert ("MCP_MPN" in users) == (operation == "set")
                if operation == "set":
                    assert users["MCP_MPN"] == value
                report["cases"].append({"plan": plan, "key": key, "result": result})
                await call("capture_close", {"sessionId": current["sessionId"]})
                current = next_session
            report["displayCases"] = []
            for index, mode in enumerate((0, 3, 4)):
                part_id = await selected_part(current)
                location = [-55 + index * 5, 42 + index * 3]
                rotation = index + 1
                plan = await call("capture_plan_display_property", {"sessionId": current["sessionId"], "partId": part_id,
                    "propertyName": "Value", "location": location, "rotationCode": rotation, "displayTypeCode": mode})
                result = await call("capture_apply_display_property", {"planId": plan["planId"], "planDigest": plan["planDigest"], "idempotencyKey": f"display-stdio-{index}"})
                assert result["observedDisplay"]["location"] == location and result["observedDisplay"]["rotationCode"] == rotation
                assert result["observedDisplay"]["displayTypeCode"] == mode
                assert result["dataPropertiesPreserved"] and result["otherDisplayPropertiesPreserved"]
                opened_display = await call("capture_open_edit_result", {"planId": plan["planId"], "planDigest": plan["planDigest"], "kind": "display_property"})
                await call("capture_close", {"sessionId": current["sessionId"]})
                current = opened_display
                report["displayCases"].append({"plan": plan, "result": result})
            report["checks"]["display_hide_name_both_if_valued_position_rotation_chain"] = True
            await call("capture_close", {"sessionId": current["sessionId"]})
            report["checks"]["set_empty_delete_chained_through_mcp_only"] = True
            assert sha256(args.workspace_root / "work" / ws["workspaceId"] / "design.dsn") == before
            report["checks"]["input_workspace_unchanged"] = True
        # Durable output reopening is independent of the original in-memory workspace/session.
        async with Client(params, mode="legacy", read_timeout_seconds=90) as fresh:
            final = report["cases"][-1]
            repeated = await fresh.call_tool("capture_apply_user_property", {"planId": final["plan"]["planId"], "planDigest": final["plan"]["planDigest"], "idempotencyKey": final["key"]})
            assert not repeated.is_error and repeated.structured_content["data"] == final["result"]
            reopened = await fresh.call_tool("capture_open_edit_result", {"planId": final["plan"]["planId"], "planDigest": final["plan"]["planDigest"], "kind": "user_property"})
            assert not reopened.is_error
            sid = reopened.structured_content["data"]["sessionId"]
            assert not (await fresh.call_tool("capture_close", {"sessionId": sid})).is_error
        report["checks"]["fresh_server_idempotence_and_verified_output_reopen"] = True
        report["sourceHashAfter"] = sha256(args.source)
        assert before == report["sourceHashAfter"]
        report["checks"]["source_unchanged"] = True
        report["passed"] = True
    except Exception as error:
        report["errorType"] = type(error).__name__
        raise
    finally:
        (args.workspace_root / "objects-metadata-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.workspace_root / "objects-metadata-report.json"), "passed": report["passed"], "tools": len(tools), "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    asyncio.run(main(parser.parse_args()))
