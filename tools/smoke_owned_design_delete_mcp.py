"""SPB 24.1 stdio acceptance of ownership-checked design deletion."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256, write_json
from cadence_mcp.gui_jobs import durable_json


async def call(client, tool, args, expected_error=None):
    reply = await client.call_tool(tool, args)
    content = reply.structured_content
    if expected_error is not None:
        assert reply.is_error and content["error"]["code"] == expected_error, (tool, content or reply.content)
        return None
    assert not reply.is_error, (tool, content or reply.content)
    return content["data"]


def plan_key(plan):
    return {key: plan[key] for key in ("planId", "planDigest")}


def arguments(plan, result, kind):
    return {**plan_key(plan), "kind": kind, "expectedSha256": result["artifact"]["sha256"]}


def interrupted_intent(directory, args):
    record = directory / "plan.json"
    row = json.loads(record.read_text(encoding="utf-8"))
    artifact = row["result"]["artifact"]
    row.update(state="artifact_deletion_pending", deletion={
        **plan_key(args), "artifactId": artifact["artifactId"], "sha256": artifact["sha256"],
        "workspaceRelativePath": artifact["workspaceRelativePath"], "requestedAt": time.time(),
    })
    durable_json(record, row)


async def run(install, source, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "work"
    original = sha256(source)
    params = StdioServerParameters(command=sys.executable, args=[
        "-B", "-m", "cadence_mcp.server", "--install-root", str(install), "--workspace-root", str(workspace),
        "--read-root", str(source.parent), "--timeout-seconds", "90",
    ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    delete = "capture_delete_owned_design"
    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        plan = await call(client, "capture_plan_design_create", {"rootName": "DELETE_ROOT", "pageName": "PAGE1"})
        key = plan_key(plan)
        await call(client, delete, {**key, "kind": "design_create", "expectedSha256": "0" * 64}, "output_unverified")
        result = await call(client, "capture_apply_design_create", {**key, "idempotencyKey": "create"})
        assert result["independentReopenVerified"]
        created = workspace / result["outputWorkspaceRelativePath"]
        dsn = created / "design.dsn"
        args = arguments(plan, result, "design_create")
        await call(client, delete, {**args, "planDigest": "0" * 64}, "plan_digest_mismatch")
        await call(client, delete, {**args, "expectedSha256": "0" * 64}, "target_changed")
        await call(client, delete, {**args, "planId": "f" * 32}, "path_denied")
        await call(client, delete, {**args, "kind": "design_save_as"}, "path_denied")

        opened = await call(client, "capture_open_edit_result", {**key, "kind": "design_create"})
        await call(client, delete, args, "artifact_in_use")
        async with Client(params, mode="legacy", read_timeout_seconds=120) as peer:
            await call(peer, delete, args, "artifact_in_use")
            assert dsn.is_file()
        rows = await call(client, "capture_query", {
            "sessionId": opened["sessionId"], "entity": "schematic", "scope": {"kind": "design"},
        })
        pending = await call(client, "capture_plan_page_edit", {
            "sessionId": opened["sessionId"], "operation": "create",
            "schematicId": rows["items"][0]["objectId"], "pageName": "PAGE2",
        })
        renamed_plan = await call(client, "capture_plan_design_save_as", {
            "sessionId": opened["sessionId"], "fileName": "Renamed owned design.dsn",
        })
        renamed = await call(client, "capture_apply_design_save_as", {
            **plan_key(renamed_plan), "idempotencyKey": "owned-rename",
        })
        renamed_path = workspace / renamed["outputWorkspaceRelativePath"] / renamed["artifact"]["workspaceRelativePath"]
        assert renamed["independentReopenVerified"] and renamed_path.is_file()
        await call(client, "capture_close", {"sessionId": opened["sessionId"]})
        await call(client, delete, args, "artifact_in_use")
        await call(client, "capture_cancel_page_edit", plan_key(pending))
        sidecar = dsn.with_suffix(".dsnlck")
        sidecar.write_bytes(b"owned test lock")
        await call(client, delete, args, "artifact_in_use")
        sidecar.unlink()
        original_dsn = dsn.read_bytes()
        with dsn.open("ab") as stream:
            stream.write(b"tampered")
        await call(client, delete, args, "target_changed")
        assert dsn.read_bytes() == original_dsn + b"tampered"
        dsn.write_bytes(original_dsn)
        alias = output / "hardlink.dsn"
        os.link(dsn, alias)
        await call(client, delete, args, "target_changed")
        assert sha256(alias) == args["expectedSha256"]
        alias.unlink()
        receipt = await call(client, delete, args)
        assert receipt["state"] == "artifact_deleted" and not receipt["mutationReplayed"]
        assert not dsn.exists() and (created / "native-result.json").is_file()
        reopened = await call(client, "capture_open_edit_result", {
            **plan_key(renamed_plan), "kind": "design_save_as",
        })
        assert reopened["counts"] == opened["counts"] and sha256(renamed_path) == renamed["artifact"]["sha256"]
        await call(client, "capture_close", {"sessionId": reopened["sessionId"]})
        assert await call(client, delete, args) == receipt
        await call(client, "capture_open_edit_result", {**key, "kind": "design_create"}, "output_unverified")
        await call(client, "capture_recover_design_create", key, "recovery_not_needed")
        await call(client, "capture_apply_design_create", {**key, "idempotencyKey": "create"}, "write_not_replayed")
        dsn.write_bytes(original_dsn)
        await call(client, delete, args, "target_changed")
        assert sha256(dsn) == args["expectedSha256"]
        dsn.unlink()

        imported = await call(client, "cadence_create_workspace", {"sourceDesign": str(source)})
        opened = await call(client, "capture_open", {"workspaceId": imported["workspaceId"]})
        saved = []
        for label in ("Before", "After"):
            name = f"{label} interruption.DSN"
            plan = await call(client, "capture_plan_design_save_as", {"sessionId": opened["sessionId"], "fileName": name})
            result = await call(client, "capture_apply_design_save_as", {**plan_key(plan), "idempotencyKey": label})
            assert result["independentReopenVerified"] and result["sourceSnapshotUnchanged"]
            directory = workspace / result["outputWorkspaceRelativePath"]
            args = arguments(plan, result, "design_save_as")
            interrupted_intent(directory, args)
            if label == "After":
                (directory / name).unlink()
            saved.append((directory, name, args))
        await call(client, "capture_close", {"sessionId": opened["sessionId"]})

    async with Client(params, mode="legacy", read_timeout_seconds=120) as restarted:
        for directory, name, args in saved:
            await call(restarted, "capture_open_edit_result", {
                **plan_key(args), "kind": "design_save_as",
            }, "output_unverified")
            receipt = await call(restarted, delete, args)
            assert receipt["state"] == "artifact_deleted" and not receipt["mutationReplayed"]
            assert await call(restarted, delete, args) == receipt
            assert not (directory / name).exists()
            assert (directory / "native-result.json").is_file()
            assert sha256(directory / "source-snapshot/design.dsn") == original
        jobs = await call(restarted, "capture_design_save_as_jobs", {})
        states = {row["planId"]: row["state"] for row in jobs["jobs"]}
        assert states == {renamed_plan["planId"]: "verified", **{args["planId"]: "artifact_deleted" for _, _, args in saved}}

    assert sha256(source) == sha256(workspace / imported["workspaceId"] / "design.dsn") == original
    report = {"passed": True, "tools": len(tools), "createdDsnDeleted": True, "namedSaveAsDsnDeleted": True,
              "ownedRenameBySaveAsAndRetirement": True,
              "nativeProducerArtifactsReopened": True, "foreignPlanAndFingerprintRefused": True,
              "sameAndCrossProcessLiveSessionsRefused": True, "pendingDependencyAndNativeLockRefused": True,
              "tamperHardlinkAndReappearanceRefused": True, "retryAfterBothInterruptionBoundaries": True,
              "producerApplyRecoverAndOpenRefused": True, "sourcesAndNativeReceiptsPreserved": True}
    write_json(output / "report.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("install-root", "source", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.install_root, args.source, args.output))
