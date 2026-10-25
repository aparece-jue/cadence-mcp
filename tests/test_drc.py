import unittest

from cadence_mcp.core import CadenceError
from cadence_mcp.drc import parse_drc


class DrcReportTests(unittest.TestCase):
    header = "Date and Time : 10/22/26 15:45:54\nChecking Schematic: TEST\n"

    def test_numbered_and_unnumbered_diagnostics(self):
        data = parse_drc(self.header + "Checking Physical Rules\nERROR(ORCAP-1604): fixture conflict\n#1 ERROR(ORCAP-36002): fixture property\nWARNING(ORCAP-9999): fixture warning\n")
        self.assertEqual(data["counts"], {"error": 2, "warning": 1, "info": 0})
        self.assertEqual(data["byPhase"]["physical.error"], 2)
        self.assertEqual(data["findingStatus"], "errors_observed")

    def test_scope_and_phase_are_preserved(self):
        data = parse_drc(self.header + "Checking Electrical Rules\nINFO(ORCAP-1): first\nChecking Physical Rules\nINFO(ORCAP-2): second\nChecking Entire Design: FIXTURE\n")
        self.assertEqual(data["checkedDesignNames"], ["FIXTURE"])
        self.assertEqual(data["byPhase"], {"electrical.info": 1, "physical.info": 1})

    def test_empty_or_unrelated_reports_rejected(self):
        for text in ("", "all tests passed", "Date and Time : now\n"):
            with self.assertRaises(CadenceError): parse_drc(text)

    def test_unknown_diagnostic_format_is_incomplete(self):
        data = parse_drc(self.header + "ERROR(UNKNOWN CODE): malformed diagnostic\n")
        self.assertFalse(data["summaryComplete"])
        self.assertTrue(data["unparsedDiagnosticLines"])

    def test_no_errors_does_not_claim_pass_or_execution(self):
        data = parse_drc(self.header)
        self.assertFalse(data["executionVerified"])
        self.assertEqual(data["findingStatus"], "no_errors_observed")


if __name__ == "__main__": unittest.main()
