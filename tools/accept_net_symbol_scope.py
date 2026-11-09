"""Compare predeclared page and flat groups on private SPB 24.1 D04 fixtures."""
import argparse
import json
from pathlib import Path

from cadence_mcp.core import CadenceError, Config, sha256, write_json
from cadence_mcp.environment import run_tcl


def read(config, root, source, label, adapter, *args):
    output = root / f"{label}.json"
    run_tcl(config, adapter, [str(source), *args, str(output)], root)
    return json.loads(output.read_text(encoding="utf-8"))


def path_key(row):
    return row["pageName"], tuple(sorted(tuple(point) for point in row["points"]))


def partition(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["flatGroup"], []).append(path_key(row))
    return sorted(sorted(members) for members in groups.values())


def check_local(bindings, flat):
    expected = {(page, ((100, y), (200, y))) for page in ("PAGE_A", "PAGE_B") for y in (800, 900)}
    wires = [row for row in bindings if row["kind"] == "wire"]
    assert len(wires) == 4 and {path_key(row) for row in wires} == expected
    assert all(row["netName"] == "LOCAL_DUP" and row["group"] for row in wires)
    assert len(flat) == 4 and {path_key(row) for row in flat} == expected
    assert all(not row["isGlobal"] for row in flat)
    assert partition(flat) == [sorted(key for key in expected if key[0] == page) for page in ("PAGE_A", "PAGE_B")]
    return {"definitionLabel": "LOCAL_DUP", "wires": 4, "isolatedPageGroups": 2}


def check_leads(bindings, flat, probes):
    assert len(flat) == len(probes) == 28
    flat_by_path = {path_key(row): row for row in flat}
    wire_by_path = {path_key(row): row for row in bindings if row["kind"] == "wire"}
    assert len(wire_by_path) == len(flat_by_path) == 28
    expected_groups = {"global": [], "offpage": []}
    negatives = []
    for probe in probes:
        key = path_key({"pageName": probe["page"], "points": probe["points"]})
        row = flat_by_path[key]
        wire = wire_by_path[key]
        symbols = [symbol for symbol in bindings
                   if symbol["pageName"] == probe["page"] and symbol["kind"] == probe["kind"]
                   and symbol["name"] == probe["expectedName"]]
        if probe["mustAttach"]:
            at_hotspot = [symbol for symbol in symbols if symbol["hotSpot"] == probe["points"][0]]
            assert len(at_hotspot) == 1 and at_hotspot[0]["group"] == wire["group"] and wire["group"]
            assert row["flatName"] == wire["netName"] == probe["expectedName"]
            assert row["isGlobal"] == (probe["kind"] == "global")
            expected_groups[probe["kind"]].append(key)
        else:
            assert all(symbol["group"] != wire["group"] for symbol in symbols)
            assert not row["isGlobal"]
            negatives.append([key])
    assert partition(flat) == sorted([sorted(keys) for keys in expected_groups.values()] + negatives)
    assert {kind: len(keys) for kind, keys in expected_groups.items()} == {"global": 8, "offpage": 8}
    return {"boundGlobalLeads": 8, "boundOffpageLeads": 8, "isolatedWrongHotspots": 12, "flatGroups": 14}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "output", "local-source", "lead-source", "lead-oracle", "legacy-source"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    sources = {"local": args.local_source, "leads": args.lead_source, "legacy": args.legacy_source, "oracle": args.lead_oracle}
    inputs = {label: sha256(path) for label, path in sources.items()}
    assert inputs["oracle"] == "b28c1b8865b8ff169ec921949ccfa66752b7acac25caaf66884b809c4d1cbae0"
    assert inputs["legacy"] == "44cc70deecb57f5d951a33ce6f43ce9e66fdb7266b71a10fbbdb9cbcd0593b35"
    probes = json.loads(args.lead_oracle.read_text(encoding="utf-8"))["probes"]
    config = Config(args.install_root, root / "work", tuple(path.parent for path in sources.values()), 60)
    report = {"passed": False, "inputSha256": inputs}
    try:
        for label in ("local", "leads"):
            source = sources[label]
            bindings = read(config, root, source, f"{label}-bindings", "inspect_net_symbol_bindings.tcl")
            report[label] = {}
            for mode in ("plain", "update"):
                flat = read(config, root, source, f"{label}-{mode}", "inspect_cross_page.tcl", mode)
                report[label][mode] = check_local(bindings, flat) if label == "local" else check_leads(bindings, flat, probes)
        report["legacy"] = {}
        for mode in ("plain", "update"):
            label = f"legacy-{mode}"
            try:
                read(config, root, sources["legacy"], label, "inspect_cross_page.tcl", mode)
            except CadenceError as error:
                result = json.loads((root / f"{label}.json.error.json").read_text(encoding="utf-8"))
                assert error.code == "dbo_error" and result == {"phase": "schematic_net", "message": "missing_schematic_net"}
                report["legacy"][mode] = result
            else:
                raise AssertionError("The original failing fixture requires a new acceptance decision.")
        report["passed"] = True
    finally:
        report["inputsUnchanged"] = all(sha256(path) == inputs[label] for label, path in sources.items())
        report["passed"] &= report["inputsUnchanged"]
        write_json(root / "report.json", report)
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
