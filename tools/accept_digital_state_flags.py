"""Verify digital DAT state 26 against independent SPB 24.1 print tables and warnings."""
import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import re
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process

HEADER = """Independent digital transition and print controls
VPOWER DPWR 0 DC 5
VANALOG ANALOG 0 DC 1
RLOAD ANALOG 0 1k
.MODEL IOLOCAL UIO(DRVH=100 DRVL=100)
"""
FOOTER = """.OPTIONS DIGINITSTATE=0
.TRAN 0.1us 5us
.PRINT/DGTLCHG TRAN DIN
.PROBE
.END
"""
# Expected trace follows stimulus or equal-driver contention. PSpice converts
# R-to-F and F-to-R to X; its print table suppresses the repeated interior X.
CASES = (
    ("legal-x-low", ("0RX0Z",), "0RX0ZZ", (0, 3, 2, 0, 5, 5), None),
    ("legal-x-high", ("1FX1Z",), "1FX1ZZ", (1, 4, 2, 1, 5, 5), None),
    ("invalid-rf", ("0RF0Z",), "0RX0ZZ", (0, 3, 26, 0, 5, 5), "R -> F"),
    ("invalid-fr", ("1FR1Z",), "1FX1ZZ", (1, 4, 26, 1, 5, 5), "F -> R"),
    ("opposed-drivers", ("0011Z", "0101Z"), "0XX1ZZ", (0, 2, 2, 1, 5, 5), None),
    ("opposed-release", ("0011Z", "01Z0Z"), "0X1XZZ", (0, 2, 1, 2, 5, 5), None),
)
PRINTED_ROW = re.compile(r"^[ \t]*(\d\.\d+E[-+]\d+)[ \t]+([01XRFZ])[ \t]*$", re.M)


def stim(device, states):
    rows = "".join(f"+ {i}us {state}\n" for i, state in enumerate(states))
    return f"U{device} STIM(1,1) DPWR 0 DIN IOLOCAL\n{rows}"


def native_process(config, directory, adapter, *args):
    command = [config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / adapter, config.install_root, *args]
    result = run_owned_process(command, directory, process_env(config), config.timeout_seconds)
    assert result["state"] == "exited" and result["returnCode"] == result["remainingOwnedProcesses"] == 0, result


def native_rows(config, directory, dat, label):
    output = directory / f"{label}.json"
    native_process(config, directory, "inspect_digital_dat.tcl", dat, output, "digital_trace", "0", "DIN", ADAPTERS / "json.tcl")
    receipt = json.loads(output.read_text(encoding="utf-8"))
    count, *fields = receipt["nativeDigitalData"].removeprefix("DIN'").split(",")
    assert int(count) * 4 == len(fields)
    return [tuple(fields[i:i + 4]) for i in range(0, len(fields), 4)]


def print_table(out):
    start = out.index("****     TRANSIENT ANALYSIS")
    end = out.index("**** Command: FINISH", start)
    return [(float(time), state) for time, state in PRINTED_ROW.findall(out[start:end])]


def check_samples(rows, states, codes):
    assert "".join(row["state"] for row in rows) == states
    assert tuple(row["nativeStateCode"] for row in rows) == codes
    assert [row["stateCode"] for row in rows] == ["01XRFZ".index(state) for state in states]
    for i, row in enumerate(rows):
        assert row["index"] == i and math.isclose(row["time"], i * 1e-6, rel_tol=0, abs_tol=1e-15)
        assert set(row) == {"index", "time", "state", "stateCode", "strengthCode", "nativeStateCode"}


async def accept(config, root, legacy_dat, legacy_out, report):
    expected_path = root / "expected.json"
    write_json(expected_path, CASES)
    expected_sha = sha256(expected_path)
    params = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "cadence_mcp.server", "--install-root", str(config.install_root),
              "--workspace-root", str(root / "mcp"), "--read-root", str(root),
              "--read-root", str(legacy_dat.parent), "--timeout-seconds", "60"],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    async with Client(params, mode="legacy", read_timeout_seconds=90) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        report["tools"] = len(tools)
        assert tools["pspice_dat_digital_samples"].input_schema["properties"]["includeVerifiedFlaggedStates"]["default"] is False

        async def call(tool, args, error=None):
            result = await client.call_tool(tool, args)
            data = result.structured_content
            if error:
                assert result.is_error and data["error"]["code"] == error and not data["data"], data
            else:
                assert not result.is_error, result.content
                return data["data"]

        for name, drivers, states, codes, hazard in CASES:
            directory = root / name
            directory.mkdir()
            circuit = directory / "input.cir"
            circuit.write_text(HEADER + "".join(stim(str(i + 1), state) for i, state in enumerate(drivers)) + FOOTER, encoding="ascii")
            source_sha = sha256(circuit)
            native_process(config, directory, "pspice_engine_analysis.tcl", circuit, directory, "transient")
            receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            assert receipt["caught"] == 0
            assert all(receipt["returns"][key] == "0" for key in ("setupReturn", "analysisReturn", "finishReturn", "cleanupReturn"))
            dat = directory / "result.dat"
            dat_sha = sha256(dat)
            out = (directory / "result.out").read_text(encoding="cp1252")
            expected_print = [(i * 1e-6, state) for i, state in enumerate(states) if (name, i) != ("opposed-drivers", 2)]
            printed = print_table(out)
            assert len(printed) == len(expected_print)
            assert all(math.isclose(t, expected_t, abs_tol=1e-15) and state == expected_state
                       for (t, state), (expected_t, expected_state) in zip(printed, expected_print))
            if hazard:
                assert f'INVALID TRANSITION Hazard at time 2us\n  on node "DIN".\n  {hazard} transition not allowed; changed to X' in out
            else:
                assert "INVALID TRANSITION Hazard" not in out
            snapshots = [native_rows(config, directory, dat, f"native-{n}") for n in range(3)]
            first = [row[:3] for row in snapshots[0]]
            assert all([row[:3] for row in snapshot] == first for snapshot in snapshots)
            assert tuple(int(row[2]) for row in first) == codes
            tail_versions = len({tuple(row[3] for row in snapshot) for snapshot in snapshots})

            ident = (await call("pspice_dat_open", {"sourceDat": str(dat)}))["datId"]
            base = {"datId": ident, "block": 0, "traceName": "DIN"}
            if hazard:
                await call("pspice_dat_digital_samples", {**base, "limit": 1}, "unsupported_digital_state_flags")
            else:
                original = await call("pspice_dat_digital_samples", base)
                assert all("nativeStateCode" not in row for row in original["items"])
                assert not original["nativeFlaggedStatesSupported"]
            args = {**base, "includeVerifiedFlaggedStates": True}
            result = await call("pspice_dat_digital_samples", args)
            check_samples(result["items"], states, codes)
            assert result["total"] == 6 and result["supportedNativeFlaggedStateCodes"] == [26]
            assert not result["nativeOpaqueTailReturned"] and not result["jobAssociationVerified"]
            page = await call("pspice_dat_digital_samples", {**args, "offset": 1, "limit": 2})
            assert page["items"] == result["items"][1:3] and page["nextOffset"] == 3
            invalid = await client.call_tool("pspice_dat_digital_samples", {**args, "includeVerifiedFlaggedStates": 1})
            assert invalid.is_error
            await call("pspice_dat_close", {"datId": ident})
            await call("pspice_dat_digital_samples", args, "session_lost")
            assert sha256(circuit) == source_sha and sha256(dat) == dat_sha
            report["cases"].append({"case": name, "codeSequence": list(codes), "printRows": printed,
                "hazard": hazard, "distinctTailSequences": tail_versions,
                "threeNativeReadsStableExceptTail": True, "inputsUnchanged": True})
        old_out = legacy_out.read_text(encoding="cp1252")
        assert 'INVALID TRANSITION Hazard at time 4us\n  on node "DIN".\n  R -> F transition not allowed; changed to X' in old_out
        old_id = (await call("pspice_dat_open", {"sourceDat": str(legacy_dat)}))["datId"]
        args = {"datId": old_id, "block": 0, "traceName": "DIN"}
        await call("pspice_dat_digital_samples", {**args, "limit": 1}, "unsupported_digital_state_flags")
        result = await call("pspice_dat_digital_samples", {**args, "includeVerifiedFlaggedStates": True, "offset": 4, "limit": 1})
        sample, = result["items"]
        assert math.isclose(sample["time"], 4e-6, abs_tol=1e-15)
        assert (sample["state"], sample["stateCode"], sample["nativeStateCode"]) == ("X", 2, 26)
        report["originalFailureStillRefusedByDefaultAndOptInMatchesOut"] = True
        assert sha256(expected_path) == expected_sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "output", "legacy-dat", "legacy-out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(exist_ok=False)
    legacy = (args.legacy_dat.resolve(strict=True), args.legacy_out.resolve(strict=True))
    inputs = [sha256(path) for path in legacy]
    config = Config(args.install_root, root / "work", (root,), 60)
    report = {"passed": False, "cases": [], "legacyInputSha256": inputs}
    try:
        asyncio.run(accept(config, root, *legacy, report))
        report["passed"] = True
    finally:
        report["legacyInputsUnchanged"] = inputs == [sha256(path) for path in legacy]
        report["passed"] &= report["legacyInputsUnchanged"]
        write_json(root / "report.json", report)
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"])}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
