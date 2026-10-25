import copy,unittest
from cadence_mcp.net_symbols import symbol_rows
from cadence_mcp.core import CadenceError
class NetSymbolTests(unittest.TestCase):
 def test_only_exact_native_net_symbol_types_and_stable_names_are_returned(self):
  raw=[{'name':'GND','objectType':33},{'name':'LEFT','objectType':35},{'name':'IN','objectType':34},{'name':'Title','objectType':64}];before=copy.deepcopy(raw)
  a=symbol_rows(raw);self.assertEqual(a,symbol_rows(list(reversed(raw))));self.assertEqual([r['kind'] for r in a],['global','offpage','port']);self.assertEqual(raw,before)
 def test_wrong_types_fields_and_control_names_are_rejected(self):
  for raw in ([{'name':'GND','objectType':True}],[{'name':'bad\nname','objectType':33}],[{'name':'GND','objectType':33,'extra':0}],{}):
   with self.assertRaises(CadenceError):symbol_rows(raw)
 def test_casefold_ambiguity_is_rejected_but_kinds_remain_distinct(self):
  with self.assertRaises(CadenceError):symbol_rows([{'name':'GND','objectType':33},{'name':'gnd','objectType':33}])
  self.assertEqual(len(symbol_rows([{'name':'X','objectType':33},{'name':'X','objectType':34}])),2)
