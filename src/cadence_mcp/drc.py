"""Summarize native Capture DRC diagnostics without claiming execution/pass."""
from collections import Counter
import re

from .core import CadenceError


def parse_drc(text: str) -> dict:
    stamp = re.search(r"^Date and Time\s*:\s*(.+)$", text, re.MULTILINE)
    if not stamp or not re.search(r"^Checking (?:Schematic|Entire Design):", text, re.MULTILINE):
        raise CadenceError("unsupported_drc_report", "Missing native DRC header or checked scope.", "parse")
    diagnostic = re.compile(r"^\s*(?:#\d+\s+)?(ERROR|WARNING|INFO)\(([A-Z][A-Z0-9]*-\d+)\):\s*(.*)$")
    severity = Counter(); codes = Counter(); phases = Counter()
    section = "unspecified"; unparsed = []
    for line in text.splitlines():
        for label, name in (("Checking Electrical Rules", "electrical"),
                            ("Checking Physical Rules", "physical"),
                            ("Checking Simulation Rules", "simulation")):
            if line.strip().startswith(label): section = name
        match = diagnostic.match(line)
        if match:
            level, code, _ = match.groups()
            severity[level.lower()] += 1; codes[code] += 1
            phases[f"{section}.{level.lower()}"] += 1
        elif re.search(r"\b(?:ERROR|WARNING|INFO)\s*\(", line):
            unparsed.append(line)
    return {"reportedTimestamp": stamp.group(1).strip(),
            "checkedSchematics": sorted(set(re.findall(r"^Checking Schematic:\s*(.+)$", text, re.MULTILINE))),
            "checkedDesignNames": sorted(set(re.findall(r"^Checking Entire Design:\s*(.+?)\s*$", text, re.MULTILINE))),
            "counts": {key: severity[key] for key in ("error", "warning", "info")},
            "byCode": dict(sorted(codes.items())), "byPhase": dict(sorted(phases.items())),
            "unparsedDiagnosticLines": unparsed, "summaryComplete": not unparsed,
            "findingStatus": "errors_observed" if severity["error"] else "no_errors_observed",
            "executionVerified": False,
            "limits": ["Parsing does not prove the native command completed or used the intended design.",
                       "Zero error lines does not prove a complete or passing DRC run."]}
