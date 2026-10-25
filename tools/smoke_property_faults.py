"""Real isolated Dbo worker receipt-loss/recovery and start-window cancellation."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import CapturePropertyEdits
from cadence_mcp.core import CadenceError, Config, sha256


def main(args):
    root = args.workspace_root
    root.mkdir(parents=True, exist_ok=False)
    source = args.source
    config = Config(args.install_root, root / "work", (source.parent,), 60)
    capture = CaptureService(config)
    writer = CapturePropertyEdits(config, capture)
    before = sha256(source)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "passed": False, "checks": {}}
    try:
        ws = capture.create_workspace(str(source))
        opened = capture.open(ws["workspaceId"])
        data = capture.sessions[opened["sessionId"]]["data"]
        names = {row["objectId"]: row["name"] for row in data["schematic"]}
        pages = {row["objectId"]: row["name"] for row in data["page"]}
        part = next(row for row in data["part"] if names[row["schematicId"]] == "FULLADD" and pages[row["pageId"]] == "FULLADD" and row["reference"] == "U1")
        saved_execute = writer.execute
        lost = writer.plan(opened["sessionId"], part["objectId"], "PCB Footprint", "MCP_LOST_RECEIPT_TEST")
        calls = 0
        def lose_receipt(directory, payload, cancel, started):
            nonlocal calls
            calls += 1
            process = saved_execute(directory, payload, cancel, started)
            assert process["state"] == "exited" and process["returnCode"] == 0
            (directory / "native-result.json").unlink()
            return process
        writer.execute = lose_receipt
        try:
            writer.apply(lost["planId"], lost["planDigest"], "lost-receipt-key")
            raise AssertionError("Missing receipt must not be silently accepted")
        except CadenceError as error:
            assert writer._load(lost["planId"])[2]["state"] == "failed"
            report["receiptLossErrorCode"] = error.code
        directory = writer._load(lost["planId"])[0]
        saved_hash = sha256(directory / "design.dsn")
        fresh = CapturePropertyEdits(config, CaptureService(config))
        recovered = fresh.recover(lost["planId"], lost["planDigest"])
        assert recovered["state"] == "verified_recovered" and not recovered["nativeCompletionVerified"]
        assert recovered["independentReopenVerified"] and not recovered["mutationReplayed"]
        assert sha256(directory / "design.dsn") == saved_hash and calls == 1
        report["checks"]["receipt_loss_fresh_service_verification_no_replay"] = True
        report["recovered"] = recovered
        writer.execute = saved_execute
        cancelled = writer.plan(opened["sessionId"], part["objectId"], "PCB Footprint", "MCP_CANCEL_NATIVE_START")
        def cancel_at_start(directory, payload, cancel, started):
            def on_started(pid):
                started(pid)
                result = writer.cancel(cancelled["planId"], cancelled["planDigest"])
                assert result["cancelRequested"]
            return saved_execute(directory, payload, cancel, on_started)
        writer.execute = cancel_at_start
        try:
            writer.apply(cancelled["planId"], cancelled["planDigest"], "cancel-at-native-start")
            raise AssertionError("Start-window cancellation was not acknowledged")
        except CadenceError as error:
            assert error.code == "operation_cancelled"
        row = writer._load(cancelled["planId"])[2]
        assert row["state"] == "cancelled" and row["process"]["remainingOwnedProcesses"] == 0
        report["checks"]["real_native_worker_start_window_cancelled"] = True
        assert sha256(source) == before and sha256(capture.sessions[opened["sessionId"]]["design"]) == before
        report["checks"]["source_and_input_copy_unchanged"] = True
        report["passed"] = True
    finally:
        (root / "property-faults-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(root / "property-faults-report.json"), "passed": report["passed"], "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    main(parser.parse_args())
