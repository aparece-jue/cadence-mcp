"""Explicit native integration test using a copy of the provided sample DSN.

No installation data or source design is written. Report/output stays in the
configured workspace root, which should be a local, ignored directory.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import subprocess

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
from cadence_mcp.environment import ADAPTERS


async def main(args):
    before = sha256(args.source)
    env = os.environ.copy()
    # Supports a source checkout as well as an installed package.
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "cadence_mcp.server",
        "--install-root", str(args.install_root), "--workspace-root", str(args.workspace_root),
        "--read-root", str(args.source.parent), "--timeout-seconds", "60"], env=env)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "sourceHashBefore": before,
              "scope": "design_definitions", "transport": "stdio", "checks": {}}
    args.workspace_root.mkdir(parents=True, exist_ok=True)
    json_probe = args.workspace_root / "json-probe.tcl"
    json_probe.write_text('source [lindex $argv 0]\nfconfigure stdout -encoding utf-8\nputs [cmcp::obj value [cmcp::q [lindex $argv 1]] empty [cmcp::arr {}]]\n', encoding="utf-8")
    value = '中文|{}[]$;"\\\n\r\t\b\x01'
    cp = subprocess.run([str(args.install_root / 'tcltk/bin/tclsh.exe'), str(json_probe), str(ADAPTERS / 'json.tcl'), value], capture_output=True, timeout=10, check=True)
    assert json.loads(cp.stdout.decode('utf-8')) == {"value": value, "empty": []}
    report["checks"]["native_tcl_json_escape_roundtrip"] = True
    async with Client(params, mode="legacy", read_timeout_seconds=90) as client:
        tools = (await client.list_tools()).tools
        schemas = {tool.name: tool.output_schema for tool in tools}
        for tool in tools:
            Draft202012Validator.check_schema(tool.input_schema)
            Draft202012Validator.check_schema(tool.output_schema)
        report["tools"] = [t.name for t in tools]
        args.workspace_root.mkdir(parents=True, exist_ok=True)
        (args.workspace_root / "tools-list.json").write_text(json.dumps([t.model_dump(mode="json", by_alias=True) for t in tools], ensure_ascii=False, indent=2), encoding="utf-8")
        async def call(name, values):
            response = await client.call_tool(name, values)
            if response.is_error:
                raise RuntimeError(f"{name}: {response.structured_content or response.content}")
            Draft202012Validator(schemas[name]).validate(response.structured_content)
            return response.structured_content
        environment = await call("cadence_get_environment", {"probeLevel": "runtime"})
        report["environment"] = environment["data"]
        workspace = (await call("cadence_create_workspace", {"sourceDesign": str(args.source)}))["data"]
        opened = (await call("capture_open", {"workspaceId": workspace["workspaceId"]}))["data"]
        report["counts"] = opened["counts"]
        # Deliberately impossible locator: independent negative control only.
        # Never copy observed pin nets into an expected baseline.
        comparison = (await call("capture_compare_connections", {
            "sessionId": opened["sessionId"], "expectedRevision": opened["revision"],
            "expectationSource": "native-smoke-negative-control@1",
            "expectations": [{"schematicName": "__MCP_MISSING_SCHEMATIC__",
                              "pageName": "__MCP_MISSING_PAGE__", "reference": "__MCP_MISSING_PART__",
                              "pinNumber": "1", "connected": True, "net": "__MCP_NEGATIVE_CONTROL__"}]
        }))["data"]
        assert comparison["comparisonStatus"] == "fail"
        assert comparison["findings"][0]["reason"] == "pin_not_found"
        assert comparison["designPassed"] is None and not comparison["electricalConnectivityVerified"]
        artifact = comparison["artifact"]
        path = args.workspace_root / workspace["workspaceId"] / artifact["workspaceRelativePath"]
        assert sha256(path) == artifact["sha256"]
        report["checks"]["explicit_expected_pin_negative_control"] = True
        report["connectionComparison"] = comparison
        wiring = (await call("capture_check_wiring", {"sessionId": opened["sessionId"]}))["data"]
        assert wiring["pdfRequired"] is False and wiring["electricalConnectivityVerified"] is False
        assert wiring["revision"] == opened["revision"]
        assert wiring["wireCount"] > 0
        report["wiring"] = wiring
        report["checks"]["standalone_wiring_report_no_pdf"] = True

        report["workspaceId"] = workspace["workspaceId"]
        sid = opened["sessionId"]
        async def all_rows(entity, limit):
            rows = []; cursor = None
            while True:
                response = await call("capture_query", {"sessionId": sid, "entity": entity,
                    "scope": {"kind": "design"}, "limit": limit, "cursor": cursor})
                data = response["data"]; rows += data["items"]
                cursor = data["nextCursor"]
                if not cursor: break
            return rows
        rows = {}
        for entity in ("schematic", "page", "part", "pin"):
            rows[entity] = await all_rows(entity, 3)
            assert len(rows[entity]) == opened["counts"][entity]
            assert len({r["objectId"] for r in rows[entity]}) == len(rows[entity])
        report["checks"]["pagination_counts_and_unique_ids"] = True
        assert rows["page"] and rows["part"] and rows["pin"], "Sample must exercise real pages, parts and pins"
        page_id = rows["page"][0]["objectId"]
        page_parts = (await call("capture_query", {"sessionId": sid, "entity": "part",
            "scope": {"kind": "page", "pageId": page_id}, "limit": 1000}))["data"]["items"]
        assert page_parts == [r for r in rows["part"] if r["pageId"] == page_id]
        report["checks"]["page_scope"] = True
        reference = rows["part"][0]["reference"]
        exact = (await call("capture_query", {"sessionId": sid, "entity": "part", "scope": {"kind": "design"}, "reference": reference, "limit": 1000}))["data"]["items"]
        assert exact == [r for r in rows["part"] if r["reference"] == reference]
        report["checks"]["exact_reference_filter"] = True
        property_counts = []
        first_properties = None
        for part in rows["part"]:
            prop = (await call("capture_get_part_properties", {
                "sessionId": sid, "partId": part["objectId"]}))["data"]
            assert prop["partId"] == part["objectId"] and prop["revision"] == opened["revision"]
            assert prop["reference"] == part["reference"] and prop["count"] > 0
            assert prop["count"] == len(prop["items"])
            assert len({item["name"] for item in prop["items"]}) == prop["count"]
            property_counts.append(prop["count"])
            if first_properties is None:
                first_properties = prop
        repeat = (await call("capture_get_part_properties", {
            "sessionId": sid, "partId": rows["part"][0]["objectId"]}))["data"]
        assert repeat == first_properties
        ws_dir = args.workspace_root / workspace["workspaceId"]
        assert not list(ws_dir.glob("part-properties-*.json"))
        report["checks"]["part_effective_properties_all_definitions"] = True
        report["checks"]["part_properties_fresh_worker_repeat"] = True
        report["checks"]["part_properties_successful_transient_cleanup"] = True
        report["partPropertyCounts"] = property_counts
        snapshot = (await call("capture_snapshot", {"sessionId": sid}))["data"]
        artifact = snapshot["artifact"]
        snapshot_path = args.workspace_root / workspace["workspaceId"] / artifact["workspaceRelativePath"]
        assert sha256(snapshot_path) == artifact["sha256"]
        report["checks"]["snapshot_hash"] = True
        await call("capture_close", {"sessionId": sid})
        # A second native process must recover the same definitions from the unchanged copy.
        second = (await call("capture_open", {"workspaceId": workspace["workspaceId"]}))["data"]
        sid = second["sessionId"]
        for entity in rows:
            assert await all_rows(entity, 1000) == rows[entity]
        report["checks"]["fresh_worker_repeat_read"] = True
        await call("capture_close", {"sessionId": sid})
        denied = await client.call_tool("capture_close", {"sessionId": sid})
        assert denied.is_error and denied.structured_content["error"]["code"] == "session_lost"
        report["checks"]["closed_session_rejected"] = True
    report["sourceHashAfter"] = sha256(args.source)
    assert report["sourceHashAfter"] == before
    report["checks"]["source_unchanged"] = True
    report["notVerified"] = ["independent_expected_pin_net_table", "external_dependencies", "occurrence_connectivity", "write_save_reopen", "native_drc", "pdf", "pspice"]
    target = args.workspace_root / "native-smoke-report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(target), "counts": report["counts"], "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    asyncio.run(main(parser.parse_args()))
