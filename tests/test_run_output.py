import json
from unittest.mock import patch
import unittest
import test_pspice_runs
from cadence_mcp.core import CadenceError,sha256,write_json

class RunOutputTests(unittest.TestCase):
    setUp=test_pspice_runs.RunTests.setUp
    def fixture(self,native=True):
        p=self.runs.plan(self.sid,'dc');d,_,row=self.runs._load(p['planId'])
        out=d/'result.out';out.write_text('**** 10/23/26 *** PSpice 24.1 *** ID# 0\nWARNING(ORPSIM-1): fixture\n',encoding='ascii')
        write_json(d/'run-artifacts.json',{'files':[{'relativePath':'result.out','sha256':sha256(out)}]})
        row['state']='verified' if native else 'verified_recovered'
        result={'artifact':{'sha256':sha256(d/'run-artifacts.json')},'nativeCompletionVerified':native,'numericalAcceptanceVerified':False,'numericalAcceptanceScope':'declared_trace_rows_only'}
        return p,d,row,result
    def test_job_binding_does_not_claim_measurements_or_unrequested_numbers(self):
        p,d,row,result=self.fixture()
        with patch.object(self.runs,'_load',return_value=(d,None,row)),patch.object(self.runs,'_verified_result',return_value=result) as verify:
            value=self.runs.inspect_output(p['planId'],p['planDigest'])
        self.assertEqual(verify.call_count,2)
        self.assertTrue(value['jobAssociationVerified']);self.assertTrue(value['solverSuccessVerified'])
        self.assertEqual(value['producedByPlan'],p['planId']);self.assertIn('measurements',value['notChecked'])
        self.assertFalse(value['numericalAcceptanceVerified']);self.assertIsNone(value['designPassed'])
    def test_recovered_output_keeps_native_completion_unproven(self):
        p,d,row,result=self.fixture(False)
        with patch.object(self.runs,'_load',return_value=(d,None,row)),patch.object(self.runs,'_verified_result',return_value=result):
            value=self.runs.inspect_output(p['planId'],p['planDigest'])
        self.assertFalse(value['solverSuccessVerified']);self.assertFalse(value['nativeCompletionVerified'])
        self.assertTrue(value['jobAssociationVerified']);self.assertIn('fresh_solver_run',value['notChecked'])
    def test_digest_state_and_read_race_rejected(self):
        p,d,row,result=self.fixture()
        with patch.object(self.runs,'_load',return_value=(d,None,row)),patch.object(self.runs,'_verified_result',return_value=result) as verify:
            with self.assertRaises(CadenceError):self.runs.inspect_output(p['planId'],'wrong')
            verify.assert_not_called();row['state']='failed'
            with self.assertRaises(CadenceError):self.runs.inspect_output(p['planId'],p['planDigest'])
            row['state']='verified';(d/'result.out').write_text('**** 10/23/26 *** PSpice 24.1 *** ID# 0\nchanged')
            with self.assertRaises(CadenceError):self.runs.inspect_output(p['planId'],p['planDigest'])
