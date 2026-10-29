"""Bounded CIR/model reference preparation, independent of Capture and the solver.

The preflight resolves explicit .INC/.INCLUDE/.LIB only. It is deliberately
separate from engine syntax, model validity, and numerical acceptance.
"""
from pathlib import Path
import json
import re
import threading

from .core import CadenceError, checked_path, new_id, sha256, write_json


REFERENCE = re.compile(r'^\s*\.(INC|INCLUDE|LIB)\b(.*)$', re.IGNORECASE)
ARGUMENT = re.compile(r'''^\s*(?:"([^"\r\n]+)"|'([^'\r\n]+)'|([^\s;$]+))\s*(?:[;$].*)?$''')
FILE_DIRECTIVES = {".STMLIB", ".STIMULUS", ".LOADBIAS", ".SAVEBIAS", ".VECTOR", ".TEXT"}


def logical_lines(text):
    """Yield physical indexes and SPICE plus-continuation text; retain source bytes separately."""
    indexes, parts = [], []
    for number, line in enumerate(text.splitlines()):
        stripped = line.lstrip()
        if not stripped or stripped.startswith('*'):
            continue
        if stripped.startswith('+'):
            if not indexes:
                raise CadenceError('unsupported_reference', 'Orphan continuation before an input statement.')
            indexes.append(number)
            parts.append(stripped[1:].strip())
        else:
            if indexes:
                yield indexes, ' '.join(parts)
            indexes, parts = [number], [line]
    if indexes:
        yield indexes, ' '.join(parts)


class PSpiceInputs:
    def __init__(self, config):
        self.config = config
        self.inputs = {}
        self.lock = threading.RLock()

    def _reference(self, owner, name):
        if any(char in name for char in ("{", "}", "%", "*", "?", "\x00", "\r", "\n")):
            raise CadenceError("unsupported_reference", "Dynamic or wildcard references require a dedicated resolver.")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in name):
            raise CadenceError("unsupported_reference", "Reference filenames require valid UTF-8 even in byte-preserving mode.")
        value = Path(name)
        if value.is_absolute():
            return checked_path(str(value), self.config.read_roots)
        direct = owner.parent / value
        if direct.exists():
            return checked_path(str(direct), self.config.read_roots)
        candidates = {candidate.resolve() for root in self.config.read_roots
                      if (candidate := root / value).is_file()}
        if len(candidates) != 1:
            raise CadenceError("missing_or_ambiguous_reference", "A referenced input is missing or ambiguous in configured roots.")
        return checked_path(str(candidates.pop()), self.config.read_roots)

    def prepare(self, source_circuit: str, input_encoding: str = "utf-8", input_budget: str = "standard") -> dict:
        if input_encoding not in {"utf-8", "preserve-bytes"}:
            raise CadenceError("unsupported_encoding", "Select utf-8 or explicit preserve-bytes input handling.")
        if input_budget not in {"standard", "extended"}:
            raise CadenceError("input_limit", "Select a standard or extended input budget.")
        max_files, max_bytes = (64, 32 * 1024 * 1024) if input_budget == "standard" else (256, 64 * 1024 * 1024)
        with self.lock:
            if len(self.inputs) >= 64:
                raise CadenceError("input_limit", "At most 64 prepared inputs may be registered per server.")
            source = checked_path(source_circuit, self.config.read_roots)
            if not source.is_file() or source.suffix.lower() != ".cir":
                raise CadenceError("unsupported_input", "Provide one CIR input from a configured read root.")
            files, stack, total = {}, set(), 0
            analyses = set()

            def visit(path, depth):
                nonlocal total
                if path in stack:
                    raise CadenceError("reference_cycle", "Cyclic input references are not supported.")
                if path in files:
                    return
                if depth > 32 or len(files) >= max_files:
                    raise CadenceError("input_limit", "Reference depth or file count exceeds the limit.")
                if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
                    raise CadenceError("input_limit", "Referenced input is missing, not a file, or exceeds 8 MiB.")
                before = sha256(path)
                raw = path.read_bytes()
                total += len(raw)
                if total > max_bytes:
                    raise CadenceError("input_limit", "Total simulation inputs exceed the selected byte budget.")
                try:
                    text = raw.decode("utf-8-sig", errors="surrogateescape" if input_encoding == "preserve-bytes" else "strict")
                except UnicodeDecodeError as error:
                    raise CadenceError("unsupported_encoding", "This input resolver currently requires UTF-8/ASCII inputs.") from error
                if "\x00" in text:
                    raise CadenceError("unsupported_input", "Binary simulation inputs are not supported by this resolver.")
                if sha256(path) != before:
                    raise CadenceError("source_changed", "An input changed during preparation.")
                index = len(files)
                suffix = path.suffix.lower()
                if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
                    suffix = ".inc"
                destination = "input.cir" if path == source else f"deps/file-{index:03d}{suffix}"
                row = {"source": path, "sha256": before, "raw": raw, "text": text,
                       "relativePath": destination, "references": [],
                       "opaqueByteCount": sum(0xDC80 <= ord(char) <= 0xDCFF for char in text)}
                files[path] = row
                stack.add(path)
                for line_indexes, line in logical_lines(text):
                    number = line_indexes[0]
                    stripped = line.strip()
                    if not stripped or stripped.startswith("*"):
                        continue
                    directive = stripped.split()[0].upper()
                    if directive in FILE_DIRECTIVES:
                        raise CadenceError("unsupported_reference", "A file-reading/writing directive needs a dedicated resolver before execution.")
                    if directive in {".OP", ".DC", ".AC", ".TRAN"}:
                        analyses.add(directive[1:])
                    match = REFERENCE.match(line)
                    if not match:
                        continue
                    argument = ARGUMENT.fullmatch(match.group(2))
                    if argument is None:
                        raise CadenceError("unsupported_reference", "Explicit single-file .INC/.INCLUDE/.LIB references are required.")
                    name = next(value for value in argument.groups() if value is not None)
                    child = self._reference(path, name)
                    row["references"].append({"lineIndex": number, "continuationIndexes": line_indexes[1:], "directive": match.group(1).upper(), "target": child})
                    visit(child, depth + 1)
                stack.remove(path)

            visit(source, 0)
            main_lines = [line.strip().upper() for line in files[source]["text"].splitlines()
                          if line.strip() and not line.lstrip().startswith("*")]
            if not any(re.fullmatch(r"\.END(?:\s+\$.*)?", line) for line in main_lines):
                raise CadenceError("invalid_circuit", "The entry CIR must contain .END.")
            if not analyses:
                raise CadenceError("invalid_circuit", "No supported OP/DC/AC/TRAN analysis was found.")
            simulation_id = new_id("sim")
            directory = self.config.workspace_root / simulation_id
            directory.mkdir()
            directory = checked_path(str(directory), (self.config.workspace_root,))
            (directory / "originals").mkdir()
            manifest_files = []
            for index, (path, row) in enumerate(files.items()):
                if sha256(path) != row["sha256"]:
                    raise CadenceError("source_changed", "A referenced input changed before copying.")
                original = directory / "originals" / f"source-{index:03d}.bin"
                with original.open("xb") as stream:
                    stream.write(row["raw"])
                lines = row["text"].splitlines(keepends=input_encoding == "preserve-bytes")
                references = []
                for ref in row["references"]:
                    target = files[ref["target"]]["relativePath"]
                    # PSpice's documented absolute quoted filename syntax avoids
                    # assuming nested includes change the engine working directory.
                    resolved = (directory / target).as_posix()
                    old_line = lines[ref["lineIndex"]]
                    ending = "\r\n" if old_line.endswith("\r\n") else "\n" if old_line.endswith("\n") else "\r" if old_line.endswith("\r") else ""
                    lines[ref["lineIndex"]] = f'.{ref["directive"]} "{resolved}"' + (ending if input_encoding == "preserve-bytes" else "")
                    for continued in ref.get("continuationIndexes", []):
                        old = lines[continued]
                        lines[continued] = ("\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else "\r" if old.endswith("\r") else "") if input_encoding == "preserve-bytes" else ""
                    references.append({"line": ref["lineIndex"] + 1, "directive": ref["directive"], "targetRelativePath": target})
                output = directory / row["relativePath"]
                output.parent.mkdir(exist_ok=True)
                if input_encoding == "preserve-bytes":
                    raw_prepared = "".join(lines).encode("utf-8", errors="surrogateescape")
                    if row["raw"].startswith(b"\xef\xbb\xbf"):
                        raw_prepared = b"\xef\xbb\xbf" + raw_prepared
                    with output.open("xb") as stream:
                        stream.write(raw_prepared)
                else:
                    with output.open("x", encoding="utf-8", newline="\n") as stream:
                        stream.write("\n".join(lines) + "\n")
                manifest_files.append({"sourcePath": str(path), "sourceSha256": row["sha256"],
                    "originalRelativePath": original.relative_to(directory).as_posix(), "relativePath": row["relativePath"],
                    "preparedSha256": sha256(output), "size": output.stat().st_size, "references": references,
                    "inputEncoding": input_encoding, "opaqueByteCount": row["opaqueByteCount"]})
            # Snapshot all originals again to reject changes across closure traversal.
            if any(sha256(path) != row["sha256"] for path, row in files.items()):
                raise CadenceError("source_changed", "A source changed while its reference closure was being prepared.")
            manifest = {"simulationId": simulation_id, "entryRelativePath": "input.cir", "files": manifest_files,
                        "inputEncoding": input_encoding, "inputBudget": input_budget,
                        "inputLimits": {"files": max_files, "totalBytes": max_bytes, "fileBytes": 8 * 1024 * 1024, "depth": 32}, "analyses": sorted(analyses), "fileCount": len(files), "sourceFingerprint": files[source]["sha256"],
                        "referenceResolver": "explicit-inc-include-lib@0.1.0", "inputEngineVerified": False,
                        "notChecked": ["engine_syntax", "model_validity", "ground_semantics", "numerical_results",
                                       "implicit_or_embedded_file_references", "opaque_byte_engine_interpretation" if input_encoding == "preserve-bytes" else "non_utf8_inputs"]}
            write_json(directory / "input-manifest.json", manifest)
            self.inputs[simulation_id] = {"directory": directory, "manifest": manifest, "manifestHash": sha256(directory / "input-manifest.json")}
            return {key: manifest[key] for key in ("simulationId", "inputEncoding", "inputBudget", "inputLimits", "entryRelativePath", "analyses", "fileCount", "sourceFingerprint", "referenceResolver", "inputEngineVerified", "notChecked")}

    def get(self, simulation_id):
        with self.lock:
            row = self.inputs.get(simulation_id)
            if row is None:
                raise CadenceError("simulation_not_found", "Prepared input is unknown in this server instance.")
            directory = checked_path(str(row["directory"]), (self.config.workspace_root,))
            if sha256(checked_path(str(directory / "input-manifest.json"), (directory,))) != row["manifestHash"]:
                raise CadenceError("target_changed", "Prepared input manifest changed.")
            for file in row["manifest"]["files"]:
                target = checked_path(str(directory / file["relativePath"]), (directory,))
                original = checked_path(str(directory / file["originalRelativePath"]), (directory,))
                if sha256(target) != file["preparedSha256"] or sha256(original) != file["sourceSha256"]:
                    raise CadenceError("target_changed", "Prepared simulation inputs changed.")
            return {"simulationId": simulation_id, "inputEngineVerified": False,
                    "inputEncoding": row["manifest"].get("inputEncoding", "utf-8"), "inputBudget": row["manifest"].get("inputBudget", "standard"),
                    "entryRelativePath": row["manifest"]["entryRelativePath"],
                    "fileCount": row["manifest"]["fileCount"], "analyses": row["manifest"]["analyses"],
                    "sourceFingerprint": row["manifest"]["sourceFingerprint"], "preparedInputsVerified": True,
                    "manifestSha256": row["manifestHash"], "notChecked": row["manifest"]["notChecked"]}

    def close(self, simulation_id):
        with self.lock:
            if simulation_id not in self.inputs:
                raise CadenceError("simulation_not_found", "Prepared input is unknown or already closed.")
            del self.inputs[simulation_id]
            return {"simulationId": simulation_id, "closed": True, "filesDeleted": False}
