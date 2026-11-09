"""Exercise routed unit poses on the original shared-power failure fixture."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json

EXPECTED_SOURCE = "eac30125399ab21837bba639092dd1c3b8ec59fa111249687c58f9c2898f8c14"
CASES = {
    "translate": ([1000, 900], 0, 0, [[980, 900], [1020, 900], [1000, 880]]),
    "rotate": ([1020, 900], 1, 0, [[1020, 920], [1020, 880], [1000, 900]]),
    "mirror": ([1000, 900], 0, 1, [[1020, 900], [980, 900], [1000, 880]]),
}


async def accept(install, source, root, report):
    oracle = root / "expected.json"
    write_json(oracle, CASES)
    oracle_hash = sha256(oracle)
    params = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "cadence_mcp.server", "--install-root", str(install),
              "--workspace-root", str(root / "work"), "--read-root", str(source.parent), "--timeout-seconds", "60"],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    plans = []
    async with Client(params, mode="legacy", read_timeout_seconds=180) as client:
        report["tools"] = len((await client.list_tools()).tools)

        async def call(tool, args, error=None):
            reply = await client.call_tool(tool, args)
            if error is not None:
                assert reply.is_error and reply.structured_content["error"]["code"] == error, reply.content
                assert not reply.structured_content["data"]
                return None
            assert not reply.is_error, reply.content
            return reply.structured_content["data"]

        workspace = await call("cadence_create_workspace", {"sourceDesign": str(source)})
        session = (await call("capture_open", {"workspaceId": workspace["workspaceId"]}))["sessionId"]
        def query(entity):
            return call("capture_query", {"sessionId": session, "entity": entity, "scope": {"kind": "design"}, "limit": 1000})

        parts = (await query("part"))["items"]
        target = None
        for part in parts:
            if part["reference"] == "U501":
                geometry = await call("capture_get_part_geometry", {"sessionId": session, "partId": part["objectId"]})
                if geometry["location"] == [1000, 700]:
                    target = part
                    break
        assert target is not None
        pins = [p for p in (await query("pin"))["items"] if p["pageId"] == target["pageId"]]
        power = [p for p in pins if p["reference"] == "U501" and p["number"] == "8"]
        assert len(power) == 3 and all(p["connected"] and p["net"] == "VCC" for p in power)
        pin = next(p for p in power if p["partId"] == target["objectId"])
        wires = (await call("capture_query_connections", {"sessionId": session, "entity": "wire", "limit": 1000}))["items"]
        wire = next(w for w in wires if w["pageId"] == target["pageId"] and
                    sorted(w["attributes"]["points"]) == [[1000, 650], [1000, 680]])
        assert wire["attributes"]["net"] == "VCC"
        pair = {"wireId": wire["objectId"], "pinId": pin["objectId"]}
        base = {"sessionId": session, "partId": target["objectId"], "operation": "set_pose", "expectedConnections": [],
                "expectedUnitConnections": [{"pinId": p["objectId"], "connected": p["connected"],
                                              "net": p["net"] if p["connected"] else None} for p in pins]}
        for case, (location, rotation, mirror, points) in CASES.items():
            report["phase"] = case
            args = {**base, "location": location, "rotation": rotation, "mirror": mirror,
                    "expectedPins": [{"number": number, "name": name, "hotSpot": point}
                                     for (number, name), point in zip((("1", "A"), ("2", "Y"), ("8", "VCC")), points)]}
            if case == "translate":
                report["phase"] = "original-and-invalid-requests"
                original = await call("capture_plan_part_edit", args)
                key = {k: original[k] for k in ("planId", "planDigest")}
                await call("capture_apply_part_edit", {**key, "idempotencyKey": "original"}, "unit_edit_net_mismatch")
                unavailable = await client.call_tool("capture_open_edit_result", {**key, "kind": "part_edit"})
                assert unavailable.is_error
                await call("capture_plan_part_edit", {**args, "wireEnds": [pair, pair]}, "invalid_unit_wire_ends")
                foreign = next(p for p in power if p["objectId"] != pin["objectId"])
                await call("capture_plan_part_edit", {**args, "wireEnds": [{**pair, "pinId": foreign["objectId"]}]}, "invalid_unit_wire_ends")
                bad_hotspot = [{**p, "hotSpot": [1001, 880]} if p["number"] == "8" else p for p in args["expectedPins"]]
                await call("capture_plan_part_edit", {**args, "expectedPins": bad_hotspot, "wireEnds": [pair]}, "unsupported_unit_wire_end")
                contradictory = [{**row, "net": "GND"} if row["pinId"] in {p["objectId"] for p in power}
                                 else row for row in base["expectedUnitConnections"]]
                await call("capture_plan_part_edit", {**args, "expectedUnitConnections": contradictory, "wireEnds": [pair]},
                           "invalid_unit_wire_ends")
                report["originalUnroutedMoveStillRejected"] = True
                report["nonPreservingNetOracleRefused"] = True
            report["phase"] = case
            plan = await call("capture_plan_part_edit", {**args, "wireEnds": [pair]})
            move, = plan["preview"]["wireEndMoves"]
            assert plan["preview"]["unit"]["referenceDesignator"] == "U501A"
            assert move["nativeId"] == 2804 and move["net"] == "VCC"
            assert sorted(move["newPoints"]) == sorted([[1000, 650], points[-1]])
            key = {k: plan[k] for k in ("planId", "planDigest")}
            result = await call("capture_apply_part_edit", {**key, "idempotencyKey": case})
            assert all(result[k] for k in ("nativeTerminalWireEditsVerified", "nativePageNetworksVerified",
                                           "unitIdentityVerified", "pageGeometryVerified", "valueFootprintPreserved",
                                           "cachePinMetadataVerified", "expectedDefinitionsVerified"))
            reopened = (await call("capture_open_edit_result", {**key, "kind": "part_edit"}))["sessionId"]
            result_pins = (await call("capture_query", {"sessionId": reopened, "entity": "pin", "limit": 1000,
                                                        "scope": {"kind": "design"}, "reference": "U501"}))["items"]
            shared = [p for p in result_pins if p["number"] == "8"]
            assert len(shared) == 3 and all(p["connected"] and p["net"] == "VCC" for p in shared)
            report["cases"].append({"case": case, "move": move, "result": result, "sharedPowerDefinitions": len(shared)})
            plans.append((case, key))
            print(f"{case}: native route and shared VCC verified", flush=True)

    report["phase"] = "fresh-server"
    async with Client(params, mode="legacy", read_timeout_seconds=180) as client:
        for case, key in plans:
            result = await client.call_tool("capture_apply_part_edit", {**key, "idempotencyKey": case})
            assert not result.is_error and not result.structured_content["data"]["mutationReplayed"]
            reopened = await client.call_tool("capture_open_edit_result", {**key, "kind": "part_edit"})
            assert not reopened.is_error
    report["freshNoReplayVerified"] = True
    report["oracleUnchanged"] = sha256(oracle) == oracle_hash
    assert report["oracleUnchanged"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "source", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    assert sha256(source) == EXPECTED_SOURCE
    root = args.output.resolve()
    root.mkdir(exist_ok=False)
    report = {"passed": False, "cases": [], "sourceSha256": EXPECTED_SOURCE}
    try:
        asyncio.run(accept(args.install_root, source, root, report))
        report["passed"] = True
    finally:
        report["sourceUnchanged"] = sha256(source) == EXPECTED_SOURCE
        report["passed"] &= report["sourceUnchanged"]
        write_json(root / "report.json", report)
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"])}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
