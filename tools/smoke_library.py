"""Native stdio OLB read acceptance; optional independently specified pin oracle."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256


async def main(args):
    before = sha256(args.source)
    args.workspace_root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "cadence_mcp.server",
        "--install-root", str(args.install_root), "--workspace-root", str(args.workspace_root),
        "--read-root", str(args.source.parent), "--timeout-seconds", "60"], env=env)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "sourceHashBefore": before,
              "transport": "stdio", "checks": {}, "scope": "library_device_definitions"}
    # Persist failures as well; never replace a failed run with a success summary.
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
            opened = await call("capture_library_open", {"sourceLibrary": str(args.source)})
            lid = opened["libraryId"]
            report["counts"] = opened["counts"]
            async def query_all(entity):
                rows, cursor = [], None
                while True:
                    page = await call("capture_library_query", {"libraryId": lid, "entity": entity,
                                      "cursor": cursor, "limit": 17})
                    rows.extend(page["items"])
                    cursor = page["nextCursor"]
                    if cursor is None:
                        break
                assert len(rows) == opened["counts"][entity]
                return rows
            rows = {kind: await query_all(kind) for kind in opened["counts"]}
            report["checks"]["all_entities_pagination_counts"] = True
            if args.expected_package:
                pins = (await call("capture_library_query", {"libraryId": lid, "entity": "pin",
                        "packageName": args.expected_package, "limit": 1000}))["items"]
                actual = {pin["number"] for pin in pins}
                assert pins and actual == set(args.expected_pin), (args.expected_package, actual, args.expected_pin)
                report["independentOracle"] = {"package": args.expected_package,
                    "expectedPhysicalPins": args.expected_pin, "source": "explicit_predeclared_cli_fixture_oracle"}
                report["checks"]["explicit_physical_pin_oracle"] = True
            report["checks"]["source_unchanged_after_read"] = sha256(args.source) == before
            await call("capture_library_close", {"libraryId": lid})
            closed = await client.call_tool("capture_library_query", {"libraryId": lid, "entity": "pin"})
            assert closed.is_error and closed.structured_content["error"]["code"] == "session_lost"
            report["checks"]["closed_session_rejected"] = True
            second = await call("capture_library_open", {"sourceLibrary": str(args.source)})
            lid = second["libraryId"]
            for entity, first in rows.items():
                assert await query_all(entity) == first
            report["checks"]["fresh_worker_repeat"] = True
            copy = args.workspace_root / lid / "library.olb"
            assert sha256(copy) == before
            copy.write_bytes(b"explicit corruption of owned test copy")
            changed = await client.call_tool("capture_library_query", {"libraryId": lid, "entity": "pin"})
            assert changed.is_error and changed.structured_content["error"]["code"] == "target_changed"
            report["checks"]["changed_copy_rejected"] = True
            await call("capture_library_close", {"libraryId": lid})
        report["sourceHashAfter"] = sha256(args.source)
        assert report["sourceHashAfter"] == before
        report["checks"]["source_unchanged"] = True
        report["passed"] = True
    except Exception as error:
        report["passed"] = False
        report["errorType"] = type(error).__name__
        raise
    finally:
        (args.workspace_root / "library-smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.workspace_root / "library-smoke-report.json"),
                      "passed": report["passed"], "counts": report["counts"], "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--expected-package")
    parser.add_argument("--expected-pin", action="append", default=[])
    args = parser.parse_args()
    if bool(args.expected_package) != bool(args.expected_pin):
        parser.error("Expected package and physical pins must be supplied together.")
    asyncio.run(main(args))
