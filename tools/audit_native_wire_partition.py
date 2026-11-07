"""Independently reopen the two owned SPB 24.1 crossing fixtures and audit every wire."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from cadence_mcp.capture_wire import geometry_union
from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import run_tcl
from cadence_mcp.page_net_partition import page_partition


def manual_groups(joined):
    groups = [
        [[[100, 100], [300, 100]]],
        [[[100, 200], [200, 200]], [[200, 200], [200, 250]]],
        [[[100, 350], [300, 350]]],
        [[[200, 300], [200, 400]]],
        [[[400, 100], [600, 100]], [[500, 100], [500, 200]]],
        [[[400, 300], [600, 300]], [[500, 300], [700, 300]]],
        [[[400, 500], [450, 500]]],
        [[[460, 500], [550, 500]]],
    ]
    if joined:
        groups[2].extend(groups.pop(3))
    return groups


def canonical_geometry(groups):
    return sorted(geometry_union(group) for group in groups)


def audit(config, source, directory, joined, expected_sha256):
    before = sha256(source)
    assert before == expected_sha256, "Unexpected fixture bytes"
    directory.mkdir()
    expected = canonical_geometry(manual_groups(joined))
    output = directory / "native-partition.json"
    run_tcl(config, "inspect_page_net_partition.tcl", [str(source), str(output)], directory)
    rows = json.loads(output.read_text(encoding="utf-8"))
    page_partition(rows)
    assert rows and all(row["kind"] == "wire" and (row["schematicName"], row["pageName"]) == ("ROOT", "MAIN")
                        for row in rows), "Unexpected pin, page or empty output"
    native = defaultdict(list)
    for row in rows:
        native[row["group"]].append(row["points"])
    assert canonical_geometry(native.values()) == expected, "Native wire-node partition differs from the manual oracle"
    assert sha256(source) == before, "Fixture changed during inspection"
    return {"sourceSha256": before, "nodeCount": len(native), "wireCount": len(rows),
            "nativeEvidenceSha256": sha256(output), "allWireNodesMatched": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("install-root", "crossing", "junction", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = Config(args.install_root, output / "work", (args.crossing.parent, args.junction.parent), 60)
    cases = {
        "crossing": audit(config, args.crossing, output / "crossing", False,
                          "5d852a7683bb3d8b60d20a2505d856fa7c4adcd9d2de2f91b29dada242b926fe"),
        "junction": audit(config, args.junction, output / "junction", True,
                          "8184f7f92848f536e9bc7a7969b5b597fe62515b1dfe5fef1bcb814b5e599397"),
    }
    report = {"passed": True, "basis": "fresh Dbo GetNet object identities", "cases": cases}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
