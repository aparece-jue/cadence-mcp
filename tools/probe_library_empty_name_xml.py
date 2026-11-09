"""Native-only diagnostic for literal empty pin names through Capture's XML bridge."""
import argparse
import copy
import json
from pathlib import Path
import subprocess

from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import ADAPTERS, process_env, run_tcl
from cadence_mcp.library_create import actual_graph, expected_graph, validate_spec


XML_SCRIPT = r'''
if {$argc != 4} {exit 2}
lassign $argv root mode input output
if {[file exists $output]} {exit 2}
load [file join $root tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
if {$mode eq "export"} {
    set state [XMATIC_OLB2XML $input $output]
} elseif {$mode eq "import"} {
    set state [XMATIC_XML2OLB $input $output]
} else {exit 2}
if {[$state Failed]} {exit 1}
'''


def run(install, directory):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    config = Config(install, directory / "work", (directory,), 60)
    spec = validate_spec({
        "packageName": "MCP_XML_PIN", "referenceTemplate": "J?", "footprint": "MCP_TEST_FP",
        "expectedHomogeneous": True,
        "symbols": [{"cellName": "MCP_XML_PIN_CELL", "partName": "MCP_XML_PIN_CELL.Normal", "lines": [],
                     "pins": [{"position": i, "name": name, "pinType": i,
                               "start": [0, i * 10], "hotSpot": [-10, i * 10], "visible": i == 0}
                              for i, name in enumerate(("PIN_SLOT", "CONTROL"))]}],
        "devices": [{"designator": "", "position": 0, "cellName": "MCP_XML_PIN_CELL",
                     "mapping": [{"position": i, "number": str(i + 1), "shared": False, "swapId": 0}
                                 for i in range(2)]}],
    })
    declaration = directory / "declaration.json"
    write_json(declaration, spec)
    original = directory / "original.olb"
    run_tcl(config, "create_library.tcl", [str(declaration), str(original), str(directory / "receipt.json")], directory)
    start = sha256(original)
    original_graph = directory / "original-graph.json"
    run_tcl(config, "inspect_library_create.tcl", [str(original), str(original_graph), "100000", "0"], directory)
    assert actual_graph(json.loads(original_graph.read_text(encoding="utf-8"))) == expected_graph(spec)
    bridge = directory / "xml-bridge.tcl"
    bridge.write_text(XML_SCRIPT, encoding="utf-8")

    def xml(mode, source, target):
        # Some native XML diagnostics include internal memory text. The experiment
        # uses return codes and independently reopened files as its evidence.
        try:
            result = subprocess.run(
                [str(install / "tcltk/bin/tclsh.exe"), str(bridge), str(install), mode, str(source), str(target)],
                cwd=directory, env=process_env(config), creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35, check=False,
            )
        except subprocess.TimeoutExpired:
            return "timeout"
        return result.returncode

    exported = directory / "export.xml"
    export_code = xml("export", original, exported)
    assert export_code == 0 and exported.is_file()
    xml_bytes = exported.read_bytes()
    marker = b'name="PIN_SLOT"'
    assert xml_bytes.count(marker) == 1
    expected_empty = copy.deepcopy(spec)
    expected_empty["symbols"][0]["pins"][0]["name"] = ""
    canonicalized = copy.deepcopy(expected_empty)
    canonicalized["symbols"][0]["pins"][0]["name"] = "$PIN0"
    cases = {}
    for mode, replacement, expected in (("control", marker, spec), ("explicit-empty", b'name=""', expected_empty),
                                         ("absent-name", b"", expected_empty)):
        source = directory / f"{mode}.xml"
        source.write_bytes(xml_bytes.replace(marker, replacement, 1))
        target = directory / f"{mode}.olb"
        code = xml("import", source, target)
        entry = {"returnCode": code, "artifactProduced": target.is_file(), "exactDeclaredGraph": False}
        cases[mode] = entry
        if code != 0 or not target.is_file():
            continue
        observed = directory / f"{mode}-graph.json"
        try:
            run_tcl(config, "inspect_library_create.tcl", [str(target), str(observed), "100000", "0"], directory)
            graph = actual_graph(json.loads(observed.read_text(encoding="utf-8")))
            entry["observedNames"] = [[row[5], row[7]] for row in graph["pins"]]
            entry["exactDeclaredGraph"] = graph == expected_graph(expected)
            if mode != "control":
                entry["matchesNativePlaceholderGraph"] = graph == expected_graph(canonicalized)
        except Exception as error:
            entry["readerError"] = getattr(error, "code", type(error).__name__)
    report = {"nativeOriginalMatchesDeclaration": True, "sourceUnchanged": sha256(original) == start, "cases": cases,
              "sourceSha256": start, "exportSha256": sha256(exported)}
    write_json(directory / "report.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.install_root, args.output)
