"""Summarize an explicitly selected native report; no Cadence execution."""
import argparse
import json
from pathlib import Path

from cadence_mcp.core import sha256, write_json
from cadence_mcp.drc import parse_drc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Fail on undecodable reports rather than silently dropping diagnostic text.
    report = parse_drc(args.report.read_text(encoding="utf-8-sig"))
    report["reportSha256"] = sha256(args.report)
    report["sourceReport"] = str(args.report.resolve())
    write_json(args.output, report)
    print(json.dumps({"counts": report["counts"], "byCode": report["byCode"], "summaryComplete": report["summaryComplete"]}))


if __name__ == "__main__":
    main()
