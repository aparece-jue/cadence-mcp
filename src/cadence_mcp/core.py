"""Shared paths, errors and result contracts; no Cadence calls."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import uuid


class CadenceError(Exception):
    def __init__(self, code: str, message: str, phase: str = "preflight"):
        super().__init__(message)
        self.code, self.phase = code, phase


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def within(path: Path, root: Path) -> bool:
    return path.is_relative_to(root)


def checked_path(value: str, roots: tuple[Path, ...], *, exists: bool = True) -> Path:
    if not Path(value).is_absolute():
        raise CadenceError("path_denied", "An absolute path is required.")
    try:
        path = Path(value).resolve(strict=exists)
    except (OSError, ValueError) as e:
        raise CadenceError("path_denied", "Path is unavailable.") from e
    if not any(within(path, r) for r in roots):
        raise CadenceError("path_denied", "Path is outside the configured roots.")
    return path


@dataclass(frozen=True)
class Config:
    install_root: Path
    workspace_root: Path
    read_roots: tuple[Path, ...]
    timeout_seconds: int = 30
    gui_bridge_config: Path | None = None
    gui_bridge_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if not self.install_root.is_absolute() or not self.workspace_root.is_absolute():
            raise ValueError("Installation and workspace roots must be absolute.")
        object.__setattr__(self, "install_root", self.install_root.resolve(strict=True))
        object.__setattr__(self, "workspace_root", self.workspace_root.resolve())
        object.__setattr__(self, "read_roots", tuple(r.resolve(strict=True) for r in self.read_roots))
        if within(self.workspace_root, self.install_root) or within(self.install_root, self.workspace_root):
            raise ValueError("Workspace and installation roots must not overlap.")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("Timeout must be between 1 and 120 seconds.")
        if not (self.install_root / "tcltk/bin/tclsh.exe").is_file():
            raise ValueError("The configured installation has no tclsh.exe.")
        self.workspace_root.mkdir(parents=True, exist_ok=True)


def result(data: dict, *, backend: str = "python", level: str = "runtime_probed",
           coverage: tuple[str, ...] = (), not_checked: tuple[str, ...] = ()) -> dict:
    return {
        "schemaVersion": "1.0", "requestId": new_id("r"), "status": "succeeded",
        "data": data, "diagnostics": [], "artifacts": [], "error": None,
        "evidence": {"level": level, "backend": backend, "complete": True,
                     "coverage": list(coverage), "notChecked": list(not_checked)},
    }


def failure(error: CadenceError) -> dict:
    row = result({}, not_checked=("operation_completion",))
    row["status"] = "failed"
    row["evidence"]["complete"] = False
    row["error"] = {"code": error.code, "message": str(error), "phase": error.phase,
                    "retryable": False, "details": {},
                    "recoveryAction": (
                        "Inspect the existing isolated artifact job and recover only by verification; never resend its mutation."
                        if error.code in {"write_not_replayed","native_write_failed","write_failed","operation_cancelled"}
                        else
                        "Query capture_gui_jobs and reconcile the existing job; preserve its lock and never resend the mutation."
                        if error.code in {"state_indeterminate","write_locked","recovery_conflict","unknown_outcome"}
                        else "Resolve the modal dialog or busy GUI before preparing a new request."
                        if error.code in {"bridge_busy","gui_state_unknown"}
                        else "Discover and explicitly attach a fresh GUI session; do not replay a possibly sent write."
                        if error.code in {"session_lost","instance_replaced","bridge_unavailable"}
                        else "Inspect the configured environment and create a fresh workspace/session.")}
    return row
