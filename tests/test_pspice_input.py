import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from mcp import Client
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.server import create_server


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install = self.root / "install"
        (install / "tcltk/bin").mkdir(parents=True)
        (install / "tcltk/bin/tclsh.exe").touch()
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.source = self.inputs / "divider.cir"
        self.source.write_text("* independent divider fixture\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.OP\n.END\n", encoding="utf-8")
        self.config = Config(install, self.root / "work", (self.inputs,))
        self.service = PSpiceInputs(self.config)

    def test_folded_nested_references_keep_originals_and_remove_consumed_plus(self):
        (self.inputs/'one.lib').write_text('.INC\n+ "two.inc"\n',encoding='utf-8')
        (self.inputs/'two.inc').write_text('.PARAM R=1k\n',encoding='utf-8')
        raw=b'* title\r\n.INCLUDE\r\n* retained comment\r\n+ "one.lib"\r\n.OP\r\n.END\r\n'
        self.source.write_bytes(raw)
        for policy in ('utf-8','preserve-bytes'):
            result=self.service.prepare(str(self.source),policy)
            self.assertEqual(result['fileCount'],3)
            directory=self.service.inputs[result['simulationId']]['directory']
            self.assertEqual((directory/'originals/source-000.bin').read_bytes(),raw)
            text=(directory/'input.cir').read_text();self.assertIn('* retained comment',text)
            self.assertFalse(any(line.lstrip().startswith('+') for line in text.splitlines()))
            self.assertEqual(self.source.read_bytes(),raw)

    def test_folded_extra_reference_argument_still_refused(self):
        self.source.write_text('* title\n.INC "one.lib"\n+ "two.lib"\n.OP\n.END\n',encoding='utf-8')
        with self.assertRaises(CadenceError) as error:self.service.prepare(str(self.source))
        self.assertEqual(error.exception.code,'unsupported_reference')

    def test_folded_reference_cycle_still_refused(self):
        self.source.write_text('* title\n.INC\n+ "one.lib"\n.OP\n.END\n',encoding='utf-8')
        (self.inputs/'one.lib').write_text('.INC\n+ "divider.cir"\n',encoding='utf-8')
        with self.assertRaises(CadenceError) as error:self.service.prepare(str(self.source))
        self.assertEqual(error.exception.code,'reference_cycle')

    def test_basic_snapshot_keeps_original_and_does_not_claim_solver(self):
        before = sha256(self.source)
        prepared = self.service.prepare(str(self.source))
        self.assertEqual(prepared["analyses"], ["OP"])
        self.assertEqual(prepared["fileCount"], 1)
        self.assertFalse(prepared["inputEngineVerified"])
        sid = prepared["simulationId"]
        directory = self.service.inputs[sid]["directory"]
        self.assertEqual((directory / "originals/source-000.bin").read_bytes(), self.source.read_bytes())
        self.assertTrue(self.service.get(sid)["preparedInputsVerified"])
        self.assertEqual(before, sha256(self.source))

    def test_nested_explicit_references_spaces_and_common_dependency(self):
        (self.inputs / "model folder").mkdir()
        (self.inputs / "model folder/one.lib").write_text('.INC "../common.inc"\n.MODEL DTEST D\n', encoding="utf-8")
        (self.inputs / "common.inc").write_text(".PARAM A=1\n", encoding="utf-8")
        self.source.write_text('* test\n.INC "model folder/one.lib"\n.LIB "common.inc"\n.OP\n.END\n', encoding="utf-8")
        before = {file: sha256(file) for file in self.inputs.rglob("*") if file.is_file()}
        prepared = self.service.prepare(str(self.source))
        self.assertEqual(prepared["fileCount"], 3)
        row = self.service.inputs[prepared["simulationId"]]
        for file in row["manifest"]["files"]:
            text = (row["directory"] / file["relativePath"]).read_text(encoding="utf-8")
            for ref in file["references"]:
                destination = row["directory"] / ref["targetRelativePath"]
                self.assertIn(destination.as_posix(), text)
                self.assertTrue(destination.is_file())
        self.assertEqual(before, {file: sha256(file) for file in before})

    def test_library_inline_comments_and_no_space_comment_delimiter(self):
        library = self.inputs / "one model.lib"
        library.write_text(".MODEL DTEST D\n", encoding="utf-8")
        for directive in ('.LIB "one model.lib" ; official library comment',
                          '.INC "one model.lib";no separating space',
                          '.LIB "one model.lib" $ existing dollar comment'):
            with self.subTest(directive=directive):
                self.source.write_text(f"* comment fixture\n{directive}\n.OP\n.END\n", encoding="utf-8")
                before = sha256(self.source)
                prepared = self.service.prepare(str(self.source))
                self.assertEqual(prepared["fileCount"], 2)
                self.assertEqual(before, sha256(self.source))
                self.service.close(prepared["simulationId"])
        (self.inputs / "plain.lib").write_text(".MODEL DTEST D\n", encoding="utf-8")
        self.source.write_text("* comment fixture\n.LIB plain.lib;comment\n.OP\n.END\n", encoding="utf-8")
        self.assertEqual(self.service.prepare(str(self.source))["fileCount"], 2)

    def test_reference_comments_do_not_allow_missing_names_or_extra_arguments(self):
        for directive in ('.LIB ; no filename', '.INC $ no filename',
                          '.LIB "model.lib" extra ; not a single-file reference',
                          '.INC model.lib other.lib;comment'):
            with self.subTest(directive=directive):
                self.source.write_text(f"* rejected\n{directive}\n.OP\n.END\n", encoding="utf-8")
                with self.assertRaises(CadenceError) as error:
                    self.service.prepare(str(self.source))
                self.assertEqual(error.exception.code, "unsupported_reference")

    def test_cycle_missing_ambiguous_and_outside_references_fail(self):
        scenarios = [(".INC missing.inc", "missing_or_ambiguous_reference"),
                     (".LIB", "unsupported_reference"),
                     ('.INC "{MODEL}.lib"', "unsupported_reference"),
                     (".INC *.lib", "unsupported_reference"),
                     (".STMLIB stim.stl", "unsupported_reference")]
        outside = self.root / "outside.inc"
        outside.write_text(".PARAM A=1", encoding="utf-8")
        scenarios.append((f'.INC "{outside.as_posix()}"', "path_denied"))
        (self.inputs / "cycle.inc").write_text('.INC "divider.cir"', encoding="utf-8")
        scenarios.append(('.INC "cycle.inc"', "reference_cycle"))
        for directive, expected in scenarios:
            self.source.write_text(f"* test\n{directive}\n.OP\n.END\n", encoding="utf-8")
            with self.assertRaises(CadenceError) as error: self.service.prepare(str(self.source))
            self.assertEqual(error.exception.code, expected)
        self.assertFalse(self.service.inputs)

    def test_ambiguous_registered_root_lookup_fails(self):
        roots = [self.root / "models1", self.root / "models2"]
        for root in roots:
            root.mkdir()
            (root / "model.lib").write_text(".MODEL DTEST D", encoding="utf-8")
        service = PSpiceInputs(Config(self.config.install_root, self.root / "otherwork", (self.inputs, *roots)))
        self.source.write_text("* test\n.LIB model.lib\n.OP\n.END", encoding="utf-8")
        with self.assertRaises(CadenceError) as error: service.prepare(str(self.source))
        self.assertEqual(error.exception.code, "missing_or_ambiguous_reference")

    def test_manifest_prepared_and_original_tampering_rejected(self):
        for relative in ("input.cir", "originals/source-000.bin", "input-manifest.json"):
            sid = self.service.prepare(str(self.source))["simulationId"]
            directory = self.service.inputs[sid]["directory"]
            (directory / relative).write_bytes(b"external edit")
            with self.assertRaises(CadenceError) as error: self.service.get(sid)
            self.assertEqual(error.exception.code, "target_changed")
            self.assertTrue(self.service.close(sid)["closed"])
            self.assertTrue((directory / relative).exists())

    def test_encoding_size_entry_end_and_analysis_preflight(self):
        for content, expected in ((b"\xff\xfe\x00", "unsupported_encoding"), (b"* title\n\x00\n.OP\n.END", "unsupported_input"),
                                  (b"* title\n.OP", "invalid_circuit"), (b"* title\n.END", "invalid_circuit"),
                                  (b"x" * (8 * 1024 * 1024 + 1), "input_limit")):
            self.source.write_bytes(content)
            with self.assertRaises(CadenceError) as error: self.service.prepare(str(self.source))
            self.assertEqual(error.exception.code, expected)

    def test_explicit_byte_preservation_keeps_model_bytes_and_line_endings(self):
        raw = b"* opaque comment\x81E\r\nR1 1 0 1k\x81E\r\n* no final newline\x85"
        model = self.inputs / "legacy.lib"
        model.write_bytes(raw)
        self.source.write_bytes(b'\xef\xbb\xbf* main\r\n.LIB "legacy.lib"; comment\r\n.OP\r\n.END\r\n')
        with self.assertRaises(CadenceError) as error:
            self.service.prepare(str(self.source))
        self.assertEqual(error.exception.code, "unsupported_encoding")
        prepared = self.service.prepare(str(self.source), "preserve-bytes")
        self.assertEqual(prepared["inputEncoding"], "preserve-bytes")
        row = self.service.inputs[prepared["simulationId"]]
        dependency = row["manifest"]["files"][1]
        self.assertEqual((row["directory"] / dependency["relativePath"]).read_bytes(), raw)
        self.assertEqual(dependency["opaqueByteCount"], 3)
        main = (row["directory"] / "input.cir").read_bytes()
        self.assertTrue(main.startswith(b"\xef\xbb\xbf* main\r\n.LIB "))
        self.assertTrue(main.endswith(b"\r\n.OP\r\n.END\r\n"))
        self.assertTrue(self.service.get(prepared["simulationId"])["preparedInputsVerified"])
        self.assertIn("opaque_byte_engine_interpretation", prepared["notChecked"])
        self.assertEqual(model.read_bytes(), raw)

    def test_byte_preservation_rejects_binary_bad_reference_and_unknown_policy(self):
        for content, policy, expected in ((b"* title\n\x00\n.OP\n.END", "preserve-bytes", "unsupported_input"),
                                          (b'* title\n.INC "bad\x81.lib"\n.OP\n.END', "preserve-bytes", "unsupported_reference"),
                                          (b"* title\n.OP\n.END", "guess", "unsupported_encoding")):
            self.source.write_bytes(content)
            with self.assertRaises(CadenceError) as error:
                self.service.prepare(str(self.source), policy)
            self.assertEqual(error.exception.code, expected)
        self.assertFalse(self.service.inputs)

    def test_mcp_byte_preservation_is_explicit_and_not_engine_verification(self):
        (self.inputs / "legacy.lib").write_bytes(b"* legacy\x81E\n.MODEL DTEST D\n")
        self.source.write_text('* input\n.LIB "legacy.lib"\n.OP\n.END\n', encoding="utf-8")
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                strict = await client.call_tool("pspice_prepare", {"sourceCircuit": str(self.source)})
                self.assertTrue(strict.is_error)
                value = await client.call_tool("pspice_prepare", {"sourceCircuit": str(self.source), "inputEncoding": "preserve-bytes"})
                self.assertFalse(value.is_error)
                self.assertEqual(value.structured_content["data"]["inputEncoding"], "preserve-bytes")
                self.assertFalse(value.structured_content["data"]["inputEngineVerified"])
                invalid = await client.call_tool("pspice_prepare", {"sourceCircuit": str(self.source), "inputEncoding": "guess"})
                self.assertTrue(invalid.is_error)
        asyncio.run(exercise())

    def test_extended_budget_is_explicit_and_bounded(self):
        for i in range(256):
            (self.inputs / f"model{i}.lib").write_text(f"* model {i}\n", encoding="utf-8")
        def circuit(count):
            return "* resource fixture\n" + "".join(f'.LIB "model{i}.lib"\n' for i in range(count)) + ".OP\n.END\n"
        self.source.write_text(circuit(64), encoding="utf-8")
        with self.assertRaises(CadenceError) as error:
            self.service.prepare(str(self.source))
        self.assertEqual(error.exception.code, "input_limit")
        value = self.service.prepare(str(self.source), "utf-8", "extended")
        self.assertEqual(value["fileCount"], 65)
        self.assertEqual(value["inputLimits"]["files"], 256)
        self.assertEqual(value["inputLimits"]["totalBytes"], 64 * 1024 * 1024)
        self.source.write_text(circuit(256), encoding="utf-8")
        with self.assertRaises(CadenceError) as error:
            self.service.prepare(str(self.source), "utf-8", "extended")
        self.assertEqual(error.exception.code, "input_limit")
        with self.assertRaises(CadenceError):
            self.service.prepare(str(self.source), "utf-8", "unbounded")

    def test_reference_depth_limit_and_unknown_registration(self):
        for i in range(34):
            (self.inputs / f"m{i}.inc").write_text(f'.INC "m{i+1}.inc"\n', encoding="utf-8")
        self.source.write_text('* deep\n.INC "m0.inc"\n.OP\n.END', encoding="utf-8")
        with self.assertRaises(CadenceError) as error: self.service.prepare(str(self.source))
        self.assertEqual(error.exception.code, "input_limit")
        with self.assertRaises(CadenceError): self.service.get("foreign")
        with self.assertRaises(CadenceError): self.service.close("foreign")

    def test_mcp_prepare_get_close_and_strict_inputs(self):
        async def exercise():
            async with Client(create_server(self.config), raise_exceptions=True) as client:
                prepared = await client.call_tool("pspice_prepare", {"sourceCircuit": str(self.source)})
                self.assertFalse(prepared.is_error)
                sid = prepared.structured_content["data"]["simulationId"]
                value = await client.call_tool("pspice_get_input", {"simulationId": sid})
                self.assertTrue(value.structured_content["data"]["preparedInputsVerified"])
                extra = await client.call_tool("pspice_prepare", {"sourceCircuit": str(self.source), "exec": "no"})
                self.assertTrue(extra.is_error)
                self.assertFalse((await client.call_tool("pspice_close_input", {"simulationId": sid})).is_error)
                self.assertTrue((await client.call_tool("pspice_get_input", {"simulationId": sid})).is_error)
        asyncio.run(exercise())
