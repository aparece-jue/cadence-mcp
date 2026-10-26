import json,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.drc_configuration import decode_drc_configuration,ROWS,ONLINE
class DrcConfigurationTests(unittest.TestCase):
 def fixture(self):
  config={k:'0' for k in ONLINE};config.update(RunOnlineRules='1',RunElectricalRules='1',ERCMatrix={k:['-']*16 for k in ROWS});config['ERCMatrix']['OUT_PIN'][2]='E'
  return config
 def decode(self,c,**kw):return decode_drc_configuration({'nativeConfiguration':json.dumps(c),'onlineEnabled':True,'flowEnabled':True,**kw})
 def test_online_master_does_not_prove_rules_enabled(self):
  d=self.decode(self.fixture());self.assertTrue(d['onlineEnabled']);self.assertEqual(d['onlineElectricalEnabledCount'],0);self.assertFalse(d['rulesExecuted']);self.assertFalse(d['coverageVerified']);self.assertEqual(d['ercMatrix']['OUT_PIN'][2],'E')
 def test_flags_and_digest_change_with_configuration(self):
  c=self.fixture();before=self.decode(c);c[ONLINE[0]]='1';after=self.decode(c);self.assertEqual(after['onlineElectricalEnabledCount'],1);self.assertNotEqual(before['configurationSha256'],after['configurationSha256'])
 def test_incomplete_or_invalid_rule_values_refused(self):
  for mutation in ('missing','invalid','number'):
   c=self.fixture()
   if mutation=='missing':del c[ONLINE[0]]
   else:c[ONLINE[0]]='enabled' if mutation=='invalid' else 1
   with self.subTest(mutation=mutation),self.assertRaises(CadenceError):self.decode(c)
 def test_invalid_matrix_and_native_signals_refused(self):
  for kind in ('missing','short','severity','numeric','signal'):
   c=self.fixture();kw={}
   if kind=='missing':del c['ERCMatrix']['OUT_PIN']
   elif kind=='short':c['ERCMatrix']['OUT_PIN'].pop()
   elif kind=='severity':c['ERCMatrix']['OUT_PIN'][2]='X'
   elif kind=='numeric':c['ERCMatrix']['OUT_PIN'][2]=0
   else:kw['onlineEnabled']=1
   with self.subTest(kind=kind),self.assertRaises(CadenceError):self.decode(c,**kw)
 def test_duplicate_or_oversized_native_json_refused(self):
  for raw in ('{"ERCMatrix":{},"ERCMatrix":{}}',' '*65537):
   with self.assertRaises(CadenceError):decode_drc_configuration({'nativeConfiguration':raw,'onlineEnabled':True,'flowEnabled':True})
