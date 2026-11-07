"""Coordination for DSNs produced by the owned design lifecycle."""
from contextlib import contextmanager
import json
from pathlib import Path
import re

from .core import CadenceError, checked_path
from .gui_jobs import acquire_guard


DESIGN_PRODUCERS = {"capture_design_create", "capture_design_save_as"}
VERIFIED_STATES = {"verified", "verified_recovered"}


def owned_design_path(root, value):
    path = Path(value)
    if path.suffix.lower() != ".dsn" or not path.is_relative_to(root):
        return None
    parts = path.relative_to(root).parts
    if (len(parts) == 4 and parts[0] == "isolated-jobs" and parts[1] in DESIGN_PRODUCERS
            and re.fullmatch(r"plan-[a-f0-9]{32}", parts[2])):
        return path
    return None


def plan_design_source(payload):
    source = payload.get("sourceDesign")
    if isinstance(source, str):
        return source
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        return ""
    for source in snapshot.get("sources", []):
        if source.get("role") == "design":
            return source["path"]
    return ""


def journal_source_matches(payload, path):
    source = plan_design_source(payload)
    return bool(source) and Path(source) == path


@contextmanager
def guard_verified_design(root, target):
    directory = target.parent
    if checked_path(str(directory), (root,)) != directory:
        raise CadenceError("path_denied", "Owned design directory must resolve to its original path.")
    with acquire_guard(directory):
        record = checked_path(str(directory / "plan.json"), (directory,))
        try:
            if record.stat().st_size > 65536:
                raise ValueError("Oversized owned design journal")
            row = json.loads(record.read_text(encoding="utf-8"))
            if row["state"] not in VERIFIED_STATES:
                raise CadenceError("output_unverified", "The owned design is no longer available for use.")
            if Path(row["result"]["artifact"]["workspaceRelativePath"]) != Path(target.name):
                raise ValueError("Unexpected owned design name")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CadenceError("invalid_plan", "Invalid owned design journal.") from error
        if checked_path(str(target), (directory,)) != target:
            raise CadenceError("target_changed", "The owned design path changed.")
        yield
