"""Native stdio acceptance for independent query and input-preparation slices."""
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
    fixtures = args.workspace_root / "fixtures"
    fixtures.mkdir()
    (fixtures / "models").mkdir()
    (fixtures / "models/common.inc").write_text(".PARAM RVAL=1k\n", encoding="ascii")
    (fixtures / "models/one.lib").write_text('.INC "common.inc"\n.MODEL DTEST D\n', encoding="ascii")
    source_cir = fixtures / "divider.cir"
    source_cir.write_text('Independent input closure fixture\n.INC "models/one.lib"\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.OP\n.END\n', encoding="ascii")
    hashes = {"dsn": sha256(args.source), "cir": sha256(source_cir)}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    params = StdioServerParameters(command=sys.executable, args=["-m", "cadence_mcp.server",
        "--install-root", str(args.install_root), "--workspace-root", str(args.workspace_root / "work"),
        "--read-root", str(args.source.parent), "--read-root", str(fixtures), "--timeout-seconds", "60"], env=env)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "passed": False,
              "sourceHashesBefore": hashes, "checks": {}, "transport": "stdio"}
    try:
        async with Client(params, mode="legacy", read_timeout_seconds=90) as client:
            tools = (await client.list_tools()).tools
            names = {tool.name for tool in tools}
            assert "capture_get_hierarchy" in names and "pspice_run" not in names
            report["checks"]["registry_matches_verified_slices"] = True
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
            parts = (await call("capture_query", {"sessionId": sid, "entity": "part", "scope": {"kind": "design"}, "limit": 1000}))["items"]
            assert len(parts) == opened["counts"]["part"]
            summaries = []
            for part in parts:
                args_part = {"sessionId": sid, "partId": part["objectId"]}
                geometry = await call("capture_get_part_geometry", args_part)
                layers = await call("capture_get_property_layers", args_part)
                assert geometry["revision"] == layers["revision"] == opened["revision"]
                assert geometry["reference"] == layers["reference"] == part["reference"]
                assert not geometry["electricalConnectivityVerified"]
                assert layers["displayCoordinateSpace"] == "owner_local"
                summaries.append({"partId": part["objectId"], "reference": part["reference"],
                    "rotationCode": geometry["rotationCode"], "mirrorCode": geometry["mirrorCode"],
                    "pinCount": len(geometry["pins"]), "propertyCounts": layers["counts"]})
            repeat = await call("capture_get_part_geometry", {"sessionId": sid, "partId": parts[-1]["objectId"]})
            assert repeat == geometry
            plain = await call("capture_get_part_properties", {"sessionId": sid, "partId": parts[-1]["objectId"]})
            assert plain["items"] == layers["effective"]
            directory = args.workspace_root / "work" / ws["workspaceId"]
            assert not list(directory.glob("part-geometry-*.json"))
            assert not list(directory.glob("property-layers-*.json"))
            report["parts"] = summaries
            report["checks"]["all_part_geometry_and_property_layers"] = True
            report["checks"]["fresh_geometry_repeat_and_effective_consistency"] = True
            report["checks"]["successful_transient_cleanup"] = True
            await call("capture_close", {"sessionId": sid})
            prepared = await call("pspice_prepare", {"sourceCircuit": str(source_cir)})
            sim = prepared["simulationId"]
            assert prepared["fileCount"] == 3 and not prepared["inputEngineVerified"]
            verified = await call("pspice_get_input", {"simulationId": sim})
            assert verified["preparedInputsVerified"]
            entry = args.workspace_root / "work" / sim / "input.cir"
            entry.write_bytes(b"explicit owned test corruption")
            changed = await client.call_tool("pspice_get_input", {"simulationId": sim})
            assert changed.is_error and changed.structured_content["error"]["code"] == "target_changed"
            await call("pspice_close_input", {"simulationId": sim})
            report["checks"]["nested_input_snapshot_and_tamper_rejection"] = True
        report["sourceHashesAfter"] = {"dsn": sha256(args.source), "cir": sha256(source_cir)}
        assert report["sourceHashesAfter"] == hashes
        report["checks"]["sources_unchanged"] = True
        report["passed"] = True
    except Exception as error:
        report["errorType"] = type(error).__name__
        raise
    finally:
        (args.workspace_root / "query-extensions-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.workspace_root / "query-extensions-report.json"),
                      "passed": report["passed"], "toolCount": len(tools), "partCount": len(parts), "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--install-root", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--workspace-root", required=True, type=Path)
    asyncio.run(main(p.parse_args()))
