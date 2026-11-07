"""Verify PCB Footprint display lifecycle on a synthetic Capture fixture via stdio MCP."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from cadence_mcp.core import sha256


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    workspace = args.output / "work"
    source_hash = sha256(args.source)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-B", "-m", "cadence_mcp.server", "--install-root", str(args.install),
              "--workspace-root", str(workspace), "--read-root", str(args.source.parent), "--timeout-seconds", "90"],
        env=env,
    )

    validators = {}

    async def call(client, tool, inputs):
        reply = await client.call_tool(tool, inputs)
        assert not reply.is_error, (tool, reply.structured_content or reply.content)
        validators[tool].validate(reply.structured_content)
        return reply.structured_content["data"]

    async def reject(client, tool, inputs, code):
        reply = await client.call_tool(tool, inputs)
        assert reply.is_error and reply.structured_content["error"]["code"] == code, (tool, reply.structured_content or reply.content)

    def plan_key(plan):
        return {key: plan[key] for key in ("planId", "planDigest")}

    async def reopen(client, plan):
        return await call(client, "capture_open_edit_result", {**plan_key(plan), "kind": "display_property"})

    planner = "capture_plan_display_property"
    applier = "capture_apply_display_property"
    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 224
        for tool in tools:
            Draft202012Validator.check_schema(tool.input_schema)
            Draft202012Validator.check_schema(tool.output_schema)
            validators[tool.name] = Draft202012Validator(tool.output_schema)
        (args.output / "tools-list.json").write_text(
            json.dumps([tool.model_dump(mode="json", by_alias=True) for tool in tools], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        work = await call(client, "cadence_create_workspace", {"sourceDesign": str(args.source)})
        original = await call(client, "capture_open", {"workspaceId": work["workspaceId"]})
        sid = original["sessionId"]
        parts = await call(client, "capture_query", {"sessionId": sid, "entity": "part", "scope": {"kind": "design"}, "limit": 128})
        owner, = [row for row in parts["items"] if row["reference"] == args.reference]
        part = {"sessionId": sid, "partId": owner["objectId"]}
        base = await call(client, "capture_get_property_layers", part)
        target = {**part, "propertyName": "PCB Footprint"}
        layout = {"location": [-40, 60], "rotationCode": 1, "displayTypeCode": 2}
        create = {**target, **layout, "operation": "create"}
        await reject(client, planner, {**target, "operation": "delete"}, "display_property_not_found")
        await reject(client, planner, {**target, "operation": "create"}, "invalid_display_change")
        await reject(client, planner, {**create, "propertyName": "Value"}, "unsupported_display_lifecycle")
        cancelled = await call(client, planner, create)
        assert (await call(client, "capture_cancel_display_property", plan_key(cancelled)))["state"] == "cancelled"
        await reject(client, applier, {**plan_key(cancelled), "idempotencyKey": "cancelled"}, "write_not_replayed")

        created = await call(client, planner, create)
        create_apply = {**plan_key(created), "idempotencyKey": "create"}
        result = await call(client, applier, create_apply)
        expected = {"name": "PCB Footprint", "value": args.footprint, "location": [-40, 60],
                    "rotationCode": 1, "displayTypeCode": 2, "colorCode": 0}
        assert result["observedDisplay"] == expected and result["allDisplayFontsVerified"]
        assert result["modeledAllInstanceStateVerified"] and result["nativeCompletionVerified"]
        copied = await reopen(client, created)
        target = {**target, "sessionId": copied["sessionId"]}
        await reject(client, planner, {**create, "sessionId": copied["sessionId"]}, "display_property_exists")
        await reject(client, planner, {**target, **layout, "operation": "delete"}, "invalid_display_change")

        legacy = await call(client, planner, {**target, "rotationCode": 0})
        assert "operation" not in legacy["preview"]
        moved = await call(client, applier, {**plan_key(legacy), "idempotencyKey": "legacy"})
        assert moved["observedDisplay"] == {**expected, "rotationCode": 0}

        deleted = await call(client, planner, {**target, "operation": "delete"})
        gone = await call(client, applier, {**plan_key(deleted), "idempotencyKey": "delete"})
        assert gone["observedDisplay"] is None and gone["allDisplayFontsVerified"]
        output = await reopen(client, deleted)
        final = await call(client, "capture_get_property_layers", {**part, "sessionId": output["sessionId"]})
        for layer in ("effective", "user", "display"):
            assert final[layer] == base[layer]

    # Reproduce an interruption after the owned native save and before the
    # verified result is committed. Seed only this smoke test's private job.
    for completed in (result, moved, gone):
        record = workspace / completed["outputWorkspaceRelativePath"] / "plan.json"
        process = json.loads(record.read_text(encoding="utf-8"))["process"]
        assert process["returnCode"] == 0 and process["remainingOwnedProcesses"] == 0
    delete_dir = workspace / gone["outputWorkspaceRelativePath"]
    plan_record = delete_dir / "plan.json"
    interrupted = json.loads(plan_record.read_text(encoding="utf-8"))
    interrupted["state"] = "started"
    interrupted.pop("result")
    interrupted.pop("verifiedAt")
    plan_record.write_text(json.dumps(interrupted), encoding="utf-8")
    (delete_dir / "native-result.json").rename(delete_dir / "saved-receipt.json")
    saved_hash = sha256(delete_dir / "design.dsn")

    async with Client(params, mode="legacy", read_timeout_seconds=120) as client:
        replay = await call(client, applier, create_apply)
        assert replay["artifact"] == result["artifact"] and replay["mutationReplayed"] is False
        recovered = await call(client, "capture_recover_display_property", plan_key(deleted))
        assert recovered["state"] == "verified_recovered" and recovered["observedDisplay"] is None
        assert recovered["independentReopenVerified"] and recovered["allDisplayFontsVerified"]
        assert recovered["mutationReplayed"] is False and recovered["nativeCompletionVerified"] is False
        assert recovered["artifact"]["sha256"] == sha256(delete_dir / "design.dsn") == saved_hash
        assert not (delete_dir / "native-result.json").exists()

        # Exercise artifact tamper rejection on the separate legacy output.
        legacy_target = workspace / moved["outputWorkspaceRelativePath"] / "design.dsn"
        with legacy_target.open("ab") as stream:
            stream.write(b"tampered test artifact")
        await reject(client, applier, {**plan_key(legacy), "idempotencyKey": "legacy"}, "target_changed")
    assert sha256(args.source) == source_hash
    report = {"passed": True, "toolCount": 224, "createDeleteSaveReopen": True, "legacyLayout": True,
              "nativeInstanceStateAndFonts": True, "sourceUnchanged": True, "restartIdempotence": True,
              "pendingCancelAndInvalidInputs": True, "interruptedRecordRecovery": True,
              "terminalTamperRejected": True, "remainingOwnedWorkers": 0}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("install", "source", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--footprint", required=True)
    asyncio.run(run(parser.parse_args()))
