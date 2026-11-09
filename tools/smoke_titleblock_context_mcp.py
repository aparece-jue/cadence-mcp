"""SPB 24.1 MCP checks for native titleblock fields and declared geometry boundaries."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json


async def call(client, tool, args, error=None):
    reply = await client.call_tool(tool, args)
    result = reply.structured_content
    if error:
        assert reply.is_error and result["error"]["code"] == error, (tool, result)
        return None
    assert not reply.is_error, (tool, result or reply.content)
    return result["data"]


async def open_design(client, source):
    ws = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
    opened = await call(client, "capture_open", {"workspaceId": ws["workspaceId"]})
    sid = opened["sessionId"]
    pages = await call(client, "capture_query", {"sessionId": sid, "entity": "page", "scope": {"kind": "design"}})
    return sid, {row["name"]: row["objectId"] for row in pages["items"]}


def expected_line_findings(oracle, titles):
    def transform(pose, point):
        x, y = point
        if pose["mirrorCode"]:
            x = -x
        x, y = ((x, y), (y, -x), (-x, -y), (-y, x))[pose["rotationCode"]]
        return pose["location"][0] + x, pose["location"][1] + y

    findings = []
    for pose in oracle["poses"]:
        if pose["page"] != "MAIN":
            continue
        title, = [row for row in titles if all(row["attributes"][key] == pose[key]
                                                for key in ("location", "rotationCode", "mirrorCode"))]
        for i, point in enumerate(([-30, 10], [140, 90])):
            x, y = transform(pose, point)
            sides = [side for side, fail in (("left", x < 0), ("top", y < 0), ("right", x > 500),
                                              ("bottom", y > 400)) if fail]
            if sides:
                findings.append((title["objectId"], i, (x, y), sides))
    return sorted(findings)


async def run(install, source, sized, fulladd, oracle_path, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = {path: sha256(path) for path in (source, sized, fulladd, oracle_path)}
    assert hashes[source] == "81d3c1b03879023fb5dacaaea64ce9eeaba288851b78125c36ccfe31142c6549"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    params = ["-B", "-m", "cadence_mcp.server", "--install-root", str(install),
              "--workspace-root", str(output / "work"), "--timeout-seconds", "75"]
    for path in (source, sized, fulladd):
        params.extend(("--read-root", str(path.parent)))
    server = StdioServerParameters(command=sys.executable, args=params,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    fields = "capture_get_titleblock_fields"
    bounds = "capture_check_page_graphic_bounds"
    report = {"passed": False}
    try:
        async with Client(server, mode="legacy", read_timeout_seconds=130) as client:
            report["tools"] = len((await client.list_tools()).tools)
            sid, pages = await open_design(client, source)
            assert set(pages) == {"MAIN", "OTHER", "EMPTY"}
            titles = (await call(client, "capture_query_graphics", {
                "sessionId": sid, "entity": "titleblock", "limit": 1000,
            }))["items"]
            assert len(titles) == 9
            for row in titles:
                observed = await call(client, fields, {"sessionId": sid, "titleblockId": row["objectId"]})
                number = 1 if row["pageId"] == pages["MAIN"] else 2
                assert observed["ownerPageContext"] == {"schematicPageCount": 3, "pageNumber": number, "pageSizeName": ""}
                assert observed["nativeTitleblockFields"]["pageCount"] == observed["nativeTitleblockFields"]["pageNumber"] == 0
                assert set(observed["fieldStatus"].values()) == {"unavailable"}
                assert not observed["allGeneratedPageFieldsMatchContext"]
            await call(client, bounds, {"sessionId": sid, "pageId": pages["MAIN"], "includeTitleblocks": True},
                       "page_dimensions_unknown")
            await call(client, fields, {"sessionId": sid, "titleblockId": "foreign"}, "object_not_found")
            await call(client, "capture_close", {"sessionId": sid})
            await call(client, fields, {"sessionId": sid, "titleblockId": titles[0]["objectId"]}, "session_lost")
            report["originalRawZeroAndIndependentPageContextVerified"] = True

            sid, pages = await open_design(client, sized)
            page_args = {"sessionId": sid, "pageId": pages["MAIN"]}
            titles = (await call(client, "capture_query_graphics", {**page_args, "entity": "titleblock"}))["items"]
            for native_id, value, status in ((1, (3, 1), "matches_context"), (3, (8, 2), "differs_from_context")):
                title, = [row for row in titles if row["nativeId"] == native_id]
                result = await call(client, fields, {"sessionId": sid, "titleblockId": title["objectId"]})
                raw = result["nativeTitleblockFields"]
                assert (raw["pageCount"], raw["pageNumber"]) == value
                assert result["fieldStatus"]["pageCount"] == result["fieldStatus"]["pageNumber"] == status
            before = await call(client, bounds, page_args)
            assert before["objectsChecked"] == 0 and not before["findings"]
            observed = await call(client, bounds, {**page_args, "includeTitleblocks": True})
            assert observed["checkedBounds"] == [0, 0, 500, 400] and observed["objectsChecked"] == 40
            assert observed["scope"] == "page_comment_and_titleblock_declared_control_points"
            assert not observed["allSupportedControlPointsInBounds"] and observed["designPassed"] is None
            actual = sorted((f["titleblockId"], f["controlPointIndex"], tuple(f["point"]), f["sides"])
                            for f in observed["findings"] if f["kind"] == "line")
            assert actual and actual == expected_line_findings(oracle, titles)
            assert {f["titleblockId"] for f in observed["findings"]} <= {row["objectId"] for row in titles}
            report["savedMatchingAndStaleFieldsKeptSeparate"] = True
            report["knownPageAndTitleblockLineBoundariesVerified"] = True

            sid, pages = await open_design(client, fulladd)
            page_args = {"sessionId": sid, "pageId": pages["FULLADD"]}
            title = (await call(client, "capture_query_graphics", {**page_args, "entity": "titleblock"}))["items"][0]
            observed = await call(client, fields, {"sessionId": sid, "titleblockId": title["objectId"]})
            assert observed["ownerPageContext"] == {"schematicPageCount": 1, "pageNumber": 1, "pageSizeName": "A"}
            assert observed["nativeTitleblockFields"]["pageSize"] == "A"
            assert observed["fieldStatus"]["pageSize"] == "matches_context"
            report["standardPageSizeNameVerified"] = True
        report["passed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourcesAndOracleUnchanged"] = all(sha256(path) == before for path, before in hashes.items())
        report["passed"] &= report["sourcesAndOracleUnchanged"]
        write_json(output / "report.json", report)
        print(json.dumps(report), flush=True)
    assert report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "source", "sized", "fulladd", "oracle", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.sized, args.fulladd, args.oracle, args.output))
