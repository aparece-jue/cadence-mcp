"""Probe only the explicitly configured installation, never a supplied DLL."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import tempfile

from .core import CadenceError, Config, sha256

FILES = {
    "tclsh": "tcltk/bin/tclsh.exe", "capture": "tools/bin/Capture.exe",
    "dbo": "tools/bin/orDb_Dll_Tcl64.dll", "pspice_cli": "tools/bin/psp_cmd.exe",
    "pspice": "tools/bin/pspice.exe",
}
ADAPTERS = Path(__file__).parent / "adapters"


def process_env(config: Config) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(config.install_root / "tools/bin"),
                                  str(config.install_root / "tcltk/bin"), env.get("PATH", "")))
    return env


def run_tcl(config: Config, script: str, args: list[str], cwd: Path) -> tuple[str, str]:
    argv = [str(config.install_root / FILES["tclsh"]), str(ADAPTERS / script),
            str(config.install_root), *args]
    from .embedded_tcl import READERS, command
    if script in READERS:
        argv = command(config.install_root, script, args)
    # Tcl native DLL faults cannot be caught inside the interpreter.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            child = subprocess.run(argv, cwd=cwd, env=process_env(config), stdout=out, stderr=err,
                                   timeout=config.timeout_seconds, check=False)
        except subprocess.TimeoutExpired as e:
            raise CadenceError("timeout", "Read-only Tcl worker timed out; its process was stopped.", "worker") from e
        except OSError as e:
            raise CadenceError("worker_launch_failed", "Unable to launch the configured Tcl worker.", "worker") from e
        out.seek(0); err.seek(0)
        stdout = out.read(1_048_577)
        stderr = err.read(1_048_577)
    if max(len(stdout), len(stderr)) > 1_048_576:
        raise CadenceError("output_limit", "Worker diagnostic output exceeds the limit.", "worker")
    if child.returncode:
        # Avoid exposing raw paths, design contents or environment in tool errors.
        message = stderr.decode("utf-8", errors="replace")
        if "CADENCE_DBO_ERROR" in message:
            raise CadenceError("dbo_error", "Dbo could not inspect the copied design.", "worker")
        raise CadenceError("worker_crashed", f"Tcl worker exited with code {child.returncode}.", "worker")
    return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def inspect_environment(config: Config, runtime: bool) -> dict:
    files = {}
    for name, relative in FILES.items():
        p = config.install_root / relative
        # Resolve each path; an installation subdirectory may itself be a junction.
        if not p.resolve().is_relative_to(config.install_root):
            raise CadenceError("path_denied", "An installation file resolves outside its configured root.")
        files[name] = {"relativePath": relative, "exists": p.is_file(),
                       "sha256": sha256(p) if p.is_file() else None}
    data = {"installRoot": str(config.install_root), "files": files, "probe": None}
    if runtime:
        with tempfile.TemporaryDirectory(prefix="probe-", dir=config.workspace_root) as tmp:
            stdout, _ = run_tcl(config, "probe.tcl", [], Path(tmp))
        probe = {}
        for line in stdout.splitlines():
            if line.startswith("CMCP:"):
                key, value = line[5:].split("=", 1)
                probe[key] = value
        if probe.get("tclVersion") is None or probe.get("dboCreateSession") != "1":
            raise CadenceError("capability_unavailable", "Dbo commands were not registered by the configured interpreter.")
        data["probe"] = probe
    return data
