"""Prepare the user's PDF destination policy; this does not print a design."""
from datetime import datetime
from pathlib import Path
import re

from .core import CadenceError, checked_path

PDF_PRINTER = "Microsoft Print to PDF"


def prepare_pdf_output(project_entry: str, output_roots: tuple[Path, ...],
                       version: str | None = None, *, now: datetime | None = None) -> dict:
    """Project entry must identify an allowed working copy, not an active window."""
    project = checked_path(project_entry, output_roots)
    if not project.is_file() or project.suffix.lower() not in {".opj", ".dsn"}:
        raise CadenceError("unsupported_input", "Expected an existing OPJ or DSN working copy.")
    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%d_%H%M%S_%f")
    suffix = stamp if version is None else version
    if (not suffix or len(suffix) > 80 or suffix in {".", ".."}
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', suffix)
            or suffix != suffix.strip() or suffix.endswith(".")):
        raise CadenceError("invalid_version", "Version must be a valid Windows filename component.")
    filename = f"{project.stem}_{suffix}.pdf"
    if len(filename) > 255:
        raise CadenceError("invalid_filename", "PDF filename exceeds the supported component length.")
    directory = checked_path(str(project.parent / "pdf"), output_roots, exists=False)
    directory.mkdir(exist_ok=True)
    directory = checked_path(str(directory), output_roots)
    destination = directory / filename
    # lexists behavior also rejects dangling links at the final destination.
    if destination.exists() or destination.is_symlink():
        raise CadenceError("output_exists", "PDF destination already exists; choose a new version.")
    return {
        "projectEntry": str(project), "projectName": project.stem,
        "printerName": PDF_PRINTER, "orientation": "landscape",
        "destination": str(destination), "filename": filename,
        "version": version, "timestamp": stamp if version is None else None,
        "printingImplemented": False,
    }
