"""Real MCP checks for native occurrence memberships and fail-closed legacy input."""
import argparse
import asyncio
from collections import defaultdict
import copy
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import run_tcl


def pin(path, name, number=None, visible=None):
    return dict(instancePathSegments=path.split("/"), name=name, occurrencePhysicalNumber=number, isVisible=visible)


def group(*pins, name=None, global_=False):
    return dict(pins=list(pins), isGlobal=global_, name=name)


def fulladd_oracle():
    # The two half-adders, intermediate SUM, carry OR, and their package power pads.
    a, b = "halfadd_A", "halfadd_B"
    def aa(unit, name, number):
        return pin(f"{a}/{unit}", name, str(number))
    def bb(unit, name, number):
        return pin(f"{b}/{unit}", name, str(number))
    groups = [
        group(pin(a, "X"), aa("U3A", "I", 1), aa("U2A", "I0", 1), aa("U2C", "I1", 10)),
        group(pin(a, "Y"), aa("U3B", "I", 3), aa("U2B", "I0", 4), aa("U2C", "I0", 9),
              pin(b, "SUM"), bb("U1C", "O", 8)),
        group(pin(a, "CARRY"), aa("U2C", "O", 8), pin("U1A", "I0", "1")),
        group(pin(a, "SUM"), aa("U1B", "O", 6)),
        group(aa("U3A", "O", 2), aa("U2B", "I1", 5)),
        group(aa("U3B", "O", 4), aa("U2A", "I1", 2)),
        group(aa("U2A", "O", 3), aa("U1B", "I0", 4)),
        group(aa("U2B", "O", 6), aa("U1B", "I1", 5)),
        group(pin(b, "X"), bb("U3C", "I", 5), bb("U2D", "I0", 12), bb("U4B", "I1", 5)),
        group(pin(b, "Y"), bb("U3D", "I", 9), bb("U4A", "I0", 1), bb("U4B", "I0", 4)),
        group(pin(b, "CARRY"), bb("U4B", "O", 6), pin("U1A", "I1", "2")),
        group(bb("U3C", "O", 6), bb("U4A", "I1", 2)),
        group(bb("U3D", "O", 8), bb("U2D", "I1", 13)),
        group(bb("U2D", "O", 11), bb("U1C", "I0", 9)),
        group(bb("U4A", "O", 3), bb("U1C", "I1", 10)),
        group(pin("U1A", "O", "3"), name="CARRY_OUT"),
    ]
    units = [f"{a}/{unit}" for unit in ("U3A", "U2A", "U3B", "U2B", "U2C", "U1B")]
    units += [f"{b}/{unit}" for unit in ("U3C", "U2D", "U3D", "U4A", "U4B", "U1C")]
    units += ["U1A"]
    for name, number in (("VCC", "14"), ("GND", "7")):
        groups.append(group(*(pin(unit, name, number, False) for unit in units), name=name, global_=True))
    assert len(groups) == 18 and sum(len(node["pins"]) for node in groups) == 69
    return groups


def verify_definition_projections(install, source, directory, expected):
    """Verify the declared flat oracle against independently read page net objects."""
    out = directory / "fulladd-definition-partition.json"
    config = Config(install, directory / "definition-work", (source.parent,), 60)
    run_tcl(config, "inspect_page_net_partition.tcl", [str(source), str(out)], directory)
    rows = json.loads(out.read_text(encoding="utf-8"))
    page_groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["kind"] == "pin":
            assert row["group"] is not None
            page_groups[(row["schematicName"], row["pageName"])][row["group"]].append((row["reference"], row["name"]))
    second_units = dict(U3C="U3A", U2D="U2A", U3D="U3B", U4A="U2B", U4B="U2C", U1C="U1B")
    for context, scope in ((None, ("FULLADD", "FULLADD")),
                           ("halfadd_A", ("HALFADD", "HALFADD")), ("halfadd_B", ("HALFADD", "HALFADD"))):
        projection = []
        for node in expected:
            members = []
            for pin in node["pins"]:
                path = pin["instancePathSegments"]
                if context is None and len(path) == 1:
                    members.append((path[0], pin["name"]))
                if len(path) == 2 and path[0] == context:
                    unit = second_units[path[1]] if context == "halfadd_B" else path[1]
                    members.append((unit, pin["name"]))
            if members:
                projection.append(sorted(members))
        assert sorted(projection) == sorted(sorted(group) for group in page_groups[scope].values()), scope


async def call(client, tool, args, error=None):
    reply = await client.call_tool(tool, args)
    data = reply.structured_content
    if error is not None:
        assert reply.is_error and data["error"]["code"] == error, (tool, data or reply.content)
        assert not data["evidence"]["complete"] and not data["data"]
    else:
        assert not reply.is_error, (tool, data or reply.content)
    return data


async def open_source(client, source):
    ws = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
    return (await call(client, "capture_open", {"workspaceId": ws["data"]["workspaceId"]}))["data"]


async def run(install, fulladd, editor, legacy, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = {path: sha256(path) for path in (fulladd, editor, legacy)}
    assert inputs[fulladd] == "27c6d11ffbb8d677954d8e56eba26a4b725c677aa83a08020da682972e1ef104"
    assert inputs[legacy] == "1baf1c3e652a8d806801f098b4d14dc4fc8189d5f3b2472c513529c0235063b7"
    params = ["-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(output / "work"),
              "--timeout-seconds", "75"]
    for source in inputs:
        params.extend(("--read-root", str(source.parent)))
    server = StdioServerParameters(command=sys.executable, args=params,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    report = {"passed": False}
    expected = fulladd_oracle()
    write_json(output / "fulladd-oracle.json", expected)
    query, compare = "capture_query_occurrence_nets", "capture_compare_occurrence_nets"
    try:
        verify_definition_projections(install, fulladd, output, expected)
        report["independentDefinitionNodeProjectionsMatched"] = True
        async with Client(server, mode="legacy", read_timeout_seconds=120) as client:
            report["tools"] = len((await client.list_tools()).tools)
            opened = await open_source(client, fulladd)
            sid, revision = opened["sessionId"], opened["revision"]
            baseline = {"sessionId": sid, "expectedRevision": revision, "expectedGroups": expected, "expectedUnbound": []}
            verdict = (await call(client, compare, baseline))["data"]
            assert verdict["comparisonStatus"] == "pass" and verdict["observedPinCount"] == 69
            report["completeFulladdOraclePassed"] = True

            first = await call(client, query, {"sessionId": sid, "limit": 19})
            assert first["status"] == "partial" and not first["evidence"]["complete"]
            rows = first["data"]["items"]
            while first["data"]["nextOffset"] is not None:
                first = await call(client, query, {"sessionId": sid, "limit": 19, "offset": first["data"]["nextOffset"]})
                rows.extend(first["data"]["items"])
            assert len(rows) == 69
            private = {tuple(row["instancePathSegments"]): row for row in rows
                       if row["definitionNetName"] == "X_BAR" and row["name"] == "O"}
            assert set(private) == {("halfadd_A", "U3A"), ("halfadd_B", "U3C")}
            assert len({row["flatNetId"] for row in private.values()}) == 2
            assert all(not row["isGlobal"] for row in private.values())
            report["sameDefinitionLabelAndDistinctNativeNodes"] = True

            wrong = copy.deepcopy(expected)
            wrong[4]["pins"].extend(wrong.pop(11)["pins"])
            verdict = (await call(client, compare, {**baseline, "expectedGroups": wrong}))["data"]
            assert verdict["comparisonStatus"] == "fail" and verdict["mismatchedNodeCount"] > 0
            wrong = copy.deepcopy(expected)
            wrong[-1]["pins"][0]["isVisible"] = True
            verdict = (await call(client, compare, {**baseline, "expectedGroups": wrong}))["data"]
            assert verdict["comparisonStatus"] == "fail" and verdict["visibilityMismatchCount"] == 1
            await call(client, compare, {**baseline, "expectedRevision": "0" * 64}, "stale_revision")
            await call(client, compare, {**baseline, "expectedUnbound": [expected[0]["pins"][0]]}, "invalid_occurrence_expectations")
            await call(client, "capture_close", {"sessionId": sid})
            await call(client, query, {"sessionId": sid}, "session_lost")
            report["falseLocalMergeAndVisibilityRefused"] = True

            opened = await open_source(client, editor)
            verdict = (await call(client, compare, {
                "sessionId": opened["sessionId"], "expectedRevision": opened["revision"],
                "expectedGroups": [group(pin("R501", "B", "2"), pin("R502", "A", "1"), name="MCP_LINK")],
                "expectedUnbound": [pin("R501", "A", "1"), pin("R502", "B", "2")],
            }))["data"]
            assert verdict["comparisonStatus"] == "pass" and verdict["observedPinCount"] == 4
            report["editorConnectedResistorsPassed"] = True

            opened = await open_source(client, legacy)
            for _ in range(2):
                await call(client, query, {"sessionId": opened["sessionId"]}, "occurrence_connectivity_incomplete")
            report["originalUnresolvedNativeInputFailsClosed"] = True
        report["passed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourcesUnchanged"] = all(sha256(path) == digest for path, digest in inputs.items())
        report["passed"] &= report["sourcesUnchanged"]
        write_json(output / "report.json", report)
        print(json.dumps(report), flush=True)
    assert report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "fulladd", "editor", "legacy", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.fulladd, args.editor, args.legacy, args.output))
