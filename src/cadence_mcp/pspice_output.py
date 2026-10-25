"""Read imported PSpice OUT evidence without assigning it to a solver job."""
from pathlib import Path
import math
import re

from .core import CadenceError, checked_path, new_id, sha256, write_json
from .pspice_diagnostics import category, summary

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?"
NODE = re.compile(r"\(\s*([^()]+?)\s*\)\s*(" + NUMBER + r")(?=\s|$)")
DIAGNOSTIC = re.compile(r"^\s*(ERROR|WARNING|FATAL)(?:\(([^)]+)\))?\s*(?::|--)\s*(.*)$", re.I)
SECTION = re.compile(r"^\s*\*{4}\s+(.*?)\s*$")


def parse_out(text: str) -> dict:
    """Recognize a bounded subset; unrecognized text never proves run success."""
    if "\x00" in text:
        raise CadenceError("unsupported_encoding", "OUT contains NUL bytes.")
    diagnostics, voltages, unparsed = [], [], []
    versions, concluded = [], []
    section, bias, in_nodes = "", None, False
    for line_number, line in enumerate(text.splitlines(), 1):
        if line_number > 500000 or len(line) > 32768:
            raise CadenceError("output_limit", "OUT line count or line length exceeds the limit.")
        header = re.match(r"^\*{4}\s+.*?\*{3,}\s+PSpice\s+(.+?)\s+\*{3,}", line)
        if header and header[1] not in versions:
            versions.append(header[1])
        marker = SECTION.match(line)
        if marker:
            section = marker[1].strip()
            bias = section if section.startswith(("INITIAL TRANSIENT SOLUTION", "SMALL SIGNAL BIAS SOLUTION")) else None
            in_nodes = False
        diagnostic = DIAGNOSTIC.match(line)
        if diagnostic:
            diagnostics.append({"line": line_number, "severity": diagnostic[1].lower(),
                                "code": diagnostic[2], "message": diagnostic[3], "section": section,
                                "category": category(diagnostic[2],diagnostic[3])})
        if line.strip() == "JOB CONCLUDED":
            concluded.append(line_number)
            in_nodes = False
        if bias and re.fullmatch(r"\s*(?:NODE\s+VOLTAGE\s*)+", line):
            in_nodes = True
            continue
        if in_nodes and line.strip():
            if line.lstrip().startswith("("):
                matches = list(NODE.finditer(line))
                residue = NODE.sub("", line).strip()
                if not matches or residue:
                    unparsed.append({"line": line_number, "text": line, "section": bias})
                    continue  # Never return a partial row as fully parsed data.
                for match in matches:
                    value = float(match[2].replace("D", "E").replace("d", "e"))
                    if not math.isfinite(value):
                        raise CadenceError("invalid_numeric_result", "Non-finite OUT voltage.")
                    voltages.append({"line": line_number, "section": bias, "node": match[1].strip(),
                                     "value": value, "rawValue": match[2], "unit": "V"})
            else:
                in_nodes = False
        if len(diagnostics) + len(voltages) + len(unparsed) > 100000:
            raise CadenceError("output_limit", "OUT extracted record count exceeds the limit.")
    if not versions:
        raise CadenceError("unrecognized_output", "No supported PSpice OUT banner was found.")
    return {"format": "pspice_out_text", "reportedVersions": versions,
            "diagnostics": diagnostics, "diagnosticSummary": summary(diagnostics), "biasVoltages": voltages, "unparsedBiasRows": unparsed,
            "jobConcludedLines": concluded, "hasErrorDiagnostics": any(
                row["severity"] in ("error", "fatal") for row in diagnostics),
            "solverSuccessVerified": False, "jobAssociationVerified": False,
            "coverage": ["coded_diagnostics", "bias_node_voltage_tables", "completion_marker_observation"],
            "notChecked": ["full_diagnostic_grammar", "measurements", "dc_ac_transient_waveforms",
                           "dat", "numerical_oracle", "fresh_solver_run"]}


def inspect_output(config, source_output: str, encoding: str = "utf-8-sig") -> dict:
    if encoding not in ("utf-8-sig", "cp1252", "cp936"):
        raise CadenceError("unsupported_encoding", "Select UTF-8, cp1252 or cp936 explicitly.")
    source = checked_path(source_output, config.read_roots)
    if source.suffix.lower() != ".out" or not source.is_file():
        raise CadenceError("unsupported_input", "Provide an OUT file from configured read roots.")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise CadenceError("output_limit", "OUT exceeds 32 MiB.")
    before = sha256(source)
    with source.open("rb") as stream:
        raw = stream.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise CadenceError("output_limit", "OUT exceeds 32 MiB.")
    try:
        text = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise CadenceError("unsupported_encoding", "OUT does not match selected encoding.") from error
    import hashlib
    if hashlib.sha256(raw).hexdigest() != before or sha256(source) != before:
        raise CadenceError("source_changed", "OUT changed during inspection.")
    report = parse_out(text)
    inspection_id = new_id("pspice-output")
    directory = config.workspace_root / inspection_id
    directory.mkdir()
    directory = checked_path(str(directory), (config.workspace_root,))
    with (directory / "imported.out").open("xb") as stream:
        stream.write(raw)
    report.update({"inspectionId": inspection_id, "sourceFingerprint": before,
                   "sourcePath": str(source), "encoding": encoding, "provenance": "imported_file"})
    write_json(directory / "report.json", report)
    return {**report, "reportRelativePath": f"{inspection_id}/report.json",
            "reportSha256": sha256(directory / "report.json")}
