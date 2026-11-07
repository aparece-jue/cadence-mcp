"""Real SPB 24.1 temperature sweep DAT sampling, measurement and export."""
import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process


async def run(install, root):
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "work"
    config = Config(install, workspace, (root,), 60)
    oracle = root / "expected.json"
    expected = {"temperature": [-10, 20, 50], "parameter": [0, 1, 2], "volts": 3.0}
    write_json(oracle, expected)
    oracle_hash = sha256(oracle)
    sources = {}
    for name, analysis in (("temperature", ".DC TEMP -10 50 30"),
                           ("parameter", ".PARAM TempScale=1\n.DC PARAM TempScale 0 2 1")):
        directory = root / name
        directory.mkdir()
        circuit = directory / "input.cir"
        circuit.write_text("DAT axis unit test\nV1 IN 0 DC 6\nR1 IN OUT 1k\nR2 OUT 0 1k\n"
                           + analysis + "\n.PROBE V([OUT])\n.END\n", encoding="ascii")
        before = sha256(circuit)
        process = run_owned_process(
            [install / "tcltk/bin/tclsh.exe", ADAPTERS / "pspice_engine_analysis.tcl", install,
             circuit, directory, "dc"],
            directory, process_env(config), 60,
        )
        assert process["returnCode"] == 0 and process["remainingOwnedProcesses"] == 0, (name, process)
        assert sha256(circuit) == before
        dat = directory / "result.dat"
        sources[name] = dat, sha256(dat)

    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    params = StdioServerParameters(command=sys.executable, env=env, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(root), "--timeout-seconds", "60",
    ])

    async def call(client, tool, args):
        result = await client.call_tool(tool, args)
        assert not result.is_error, (tool, result.structured_content or result.content)
        return result.structured_content["data"]

    plans = []
    temp_unit = {"unit": "degC", "unitSource": "axis_name_convention"}
    async with Client(params, mode="legacy", read_timeout_seconds=100) as client:
        for name, axis in (("temperature", "TEMP"), ("parameter", "TempScale")):
            opened = await call(client, "pspice_dat_open", {"sourceDat": str(sources[name][0])})
            dat = {"datId": opened["datId"]}
            axis_args = {**dat, "block": 0, "traceName": axis}
            block = (await call(client, "pspice_dat_query", {**dat, "entity": "block"}))["items"][0]
            assert block["analysisName"] == "DC Sweep" and block["axis"] == axis
            traces = await call(client, "pspice_dat_query", {**dat, "entity": "trace", "block": 0})
            info = next(row for row in traces["items"] if row["name"] == axis)
            unit = temp_unit if name == "temperature" else {"unit": None, "unitSource": "unknown"}
            assert all(info[key] == value for key, value in unit.items())
            first = await call(client, "pspice_dat_samples", {**axis_args, "limit": 1})
            assert first["nextOffset"] == 1
            rest = await call(client, "pspice_dat_samples", {**axis_args, "offset": 1, "limit": 2})
            assert all(page[key] == value for page in (first, rest) for key, value in unit.items())
            assert [row["real"] for row in first["items"] + rest["items"]] == expected[name]
            if name == "temperature":
                voltage = {**axis_args, "traceName": "V(OUT)"}
                measured = await call(client, "pspice_dat_measure", voltage)
                assert measured["axisUnits"] == temp_unit and measured["valueUnits"]["unit"] == "V"
                for label, args, fmt in (("voltage", voltage, "csv"), ("temperature", axis_args, "json")):
                    plan = await call(client, "pspice_plan_dat_export", {**args, "format": fmt, "offset": 1})
                    assert plan["preview"]["axisUnits"] == temp_unit
                    assert plan["preview"]["valueUnits"]["unit"] == ("V" if label == "voltage" else "degC")
                    plans.append((label, fmt, {key: plan[key] for key in ("planId", "planDigest")}))
            await call(client, "pspice_dat_close", dat)

    async with Client(params, mode="legacy", read_timeout_seconds=100) as client:
        for label, fmt, key in plans:
            args = {**key, "idempotencyKey": label}
            exported = await call(client, "pspice_apply_dat_export", args)
            assert exported["nativeReopenVerified"]
            directory = workspace / exported["outputWorkspaceRelativePath"]
            manifest = json.loads((directory / "export-manifest.json").read_text(encoding="utf-8"))
            assert manifest["metadata"]["axisUnits"] == temp_unit
            output = (directory / ("samples." + fmt)).read_text(encoding="utf-8")
            if fmt == "csv":
                rows = list(csv.DictReader(output.splitlines()))
                assert all(abs(float(row["real"]) - expected["volts"]) <= 1e-6 for row in rows)
            else:
                exported_data = json.loads(output)
                assert exported_data["metadata"] == manifest["metadata"]
                rows = exported_data["samples"]
                assert [row["real"] for row in rows] == expected["temperature"][1:]
            assert [float(row["axisReal"]) for row in rows] == expected["temperature"][1:]
            again = await call(client, "pspice_apply_dat_export", args)
            assert again["artifact"] == exported["artifact"] and again["mutationReplayed"] is False
    assert sha256(oracle) == oracle_hash and all(sha256(path) == before for path, before in sources.values())
    report = {"passed": True, "temperatureAxis": expected["temperature"], "temperatureUnit": temp_unit,
              "genericParameterRemainsUnknown": True, "samplesAndMeasurementAccepted": True,
              "csvAndJsonVerifiedAfterRestart": True, "sourceAndOracleUnchanged": True}
    write_json(root / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.output))
