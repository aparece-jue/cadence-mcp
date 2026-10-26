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

    def test_multiline_and_inline_location_text_preserved(self):
        data = parse_drc(self.header + "Checking Electrical Rules\nERROR(ORCAP-1628): Possible pin type conflict R1,2 Output Connected to Output\n    FILTER, PAGE1 (1.80, 1.40)\nChecking Physical Rules\n#1 ERROR(ORCAP-36071): Fixture property: FILTER, PAGE1 (3.10, 5.00) .\n")
        self.assertEqual(data["locatedFindingCount"], 2)
        self.assertEqual(data["findings"][0]["message"], "Possible pin type conflict R1,2 Output Connected to Output")
        self.assertEqual(data["findings"][0]["location"]["x"], "1.80")
        self.assertEqual(data["findings"][1]["location"]["page"], "PAGE1")
        self.assertEqual(data["findings"][1]["severity"], "error")
        self.assertFalse(data["executionVerified"])

    def test_locations_are_not_carried_across_diagnostics_or_blank_lines(self):
        data = parse_drc(self.header + "ERROR(ORCAP-1): first\nWARNING(ORCAP-2): second\n\n    FILTER, PAGE1 (1.80, 1.40)\n")
        self.assertEqual(data["locatedFindingCount"], 0)
        self.assertTrue(all(f["location"] is None for f in data["findings"]))

    def test_section_labels_do_not_claim_native_rule_category(self):
        data = parse_drc(self.header + "Checking Physical Rules\nReport for Invalid References\nERROR(ORCAP-1616): Reference is invalid for this part R_load\n    FILTER, PAGE1 (3.10, 1.90)\n")
        self.assertIn("not_verified_native_rule_category", data["phaseAttribution"])
        self.assertEqual(data["findings"][0]["reportedSection"], "physical")
        self.assertEqual(data["findings"][0]["location"]["coordinateUnits"], "unspecified_native_report_units")

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
