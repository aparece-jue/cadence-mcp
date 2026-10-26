import unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.drc_configuration import decode_drc_counts,COUNTS
class DrcCountsTests(unittest.TestCase):
 def fixture(self):return {'electricalErrors':2,'electricalWarnings':0,'physicalErrors':4,'physicalWarnings':0}
 def test_observed_errors_do_not_certify_execution_or_coverage(self):
  data=decode_drc_counts(self.fixture());self.assertEqual(data['electricalErrors'],2);self.assertEqual(data['physicalErrors'],4);self.assertFalse(data['runRequested']);self.assertFalse(data['completionVerified']);self.assertFalse(data['coverageVerified']);self.assertFalse(data['atomicCrossCategorySnapshotVerified'])
 def test_zero_counts_do_not_claim_clean_design(self):
  data=decode_drc_counts(dict.fromkeys(COUNTS,0));self.assertFalse(data['completionVerified']);self.assertFalse(data['coverageVerified']);self.assertNotIn('passed',data)
 def test_invalid_counter_values_refused(self):
  for value in (-1,True,2.0,'2',2147483648,None):
   data=self.fixture();data['electricalErrors']=value
   with self.subTest(value=value),self.assertRaises(CadenceError):decode_drc_counts(data)
 def test_missing_or_extra_fields_refused(self):
  for data in ({},None,{'electricalErrors':2},{**self.fixture(),'designKey':'untrusted'}):
   with self.assertRaises(CadenceError):decode_drc_counts(data)
