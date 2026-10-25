from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from cadence_mcp.core import CadenceError
from cadence_mcp.pdf_output import prepare_pdf_output


class PdfOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.entry = self.root / "测试工程.opj"
        self.entry.write_text("fixture", encoding="utf-8")

    def plan(self, version=None, **kwargs):
        return prepare_pdf_output(str(self.entry), (self.root,), version, **kwargs)

    def test_version_printer_orientation_and_directory(self):
        result = self.plan("V1.2")
        self.assertEqual(result["printerName"], "Microsoft Print to PDF")
        self.assertEqual(result["orientation"], "landscape")
        self.assertEqual(Path(result["destination"]), self.root / "pdf" / "测试工程_V1.2.pdf")
        self.assertTrue((self.root / "pdf").is_dir())
        self.assertFalse(result["printingImplemented"])
        self.assertEqual(self.entry.read_text(encoding="utf-8"), "fixture")

    def test_timestamp_without_version(self):
        result = self.plan(now=datetime(2026,10,22,18,0,1,123456,tzinfo=timezone.utc))
        self.assertEqual(result["filename"], "测试工程_20261022_180001_123456.pdf")

    def test_collision_rejected_without_overwrite(self):
        output = Path(self.plan("V1")["destination"])
        output.write_bytes(b"existing artifact")
        with self.assertRaises(CadenceError) as error:
            self.plan("V1")
        self.assertEqual(error.exception.code, "output_exists")
        self.assertEqual(output.read_bytes(), b"existing artifact")

    def test_invalid_versions_rejected_before_creating_directory(self):
        for value in ["", "../out", "V:1", "V\\1", "V1.", " V1", "V\n1"]:
            with self.subTest(value=value), self.assertRaises(CadenceError):
                self.plan(value)
        self.assertFalse((self.root / "pdf").exists())

    def test_project_outside_output_roots_rejected(self):
        with self.assertRaises(CadenceError):
            prepare_pdf_output(str(self.entry), (self.root / "other",), "V1")

    def test_dsn_fallback_name(self):
        self.entry = self.root / "standalone.dsn"
        self.entry.write_bytes(b"fixture")
        self.assertEqual(self.plan("V2")["filename"], "standalone_V2.pdf")
