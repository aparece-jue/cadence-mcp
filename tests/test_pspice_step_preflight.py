import unittest
from cadence_mcp.pspice_runs import execution_preflight
from cadence_mcp.core import CadenceError

class StepPreflightTests(unittest.TestCase):
 def test_literal_param_list_and_original_circuit_are_accepted(self):
  execution_preflight('* own circuit\n.STEP PARAM RV LIST 500 1k\n.AC LIN 3 10 30\n.END\n')
  execution_preflight('.step param Value list -1 0 1e-3 2MEG ; literal values\n.OP')

 def test_unknown_forms_and_unbounded_or_dynamic_values_refuse(self):
  for text in ['.STEP TEMP LIST 0 27','.STEP PARAM R LIN 0 1 .1','.STEP PARAM R LIST {start} 1000',
               '.STEP PARAM R LIST 1\n+ 2','.STEP PARAM R LIST 1\n.STEP PARAM Q LIST 2',
               '.STEP PARAM R LIST '+' '.join(['1']*129),'.STEP PARAM R LIST 1 FILE=outside']:
   with self.subTest(text=text),self.assertRaises(CadenceError) as error:execution_preflight(text)
   self.assertEqual(error.exception.code,'unsupported_step_form')

 def test_existing_embedded_file_and_unknown_directive_refusals_remain(self):
  for text in ['.STEP PARAM R LIST 1\nU1 N ROM FILE=outside','.STEP PARAM R LIST 1\n.UNKNOWN']:
   with self.subTest(text=text),self.assertRaises(CadenceError):execution_preflight(text)

if __name__=='__main__':unittest.main()
