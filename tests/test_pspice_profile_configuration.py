import copy,tempfile,unittest
from pathlib import Path
from cadence_mcp.core import CadenceError
from cadence_mcp.pspice_profile_configuration import decode_selection,KEYS

class NativeProfileConfigurationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'nom.lib').write_text('* own model fixture\n')
  self.before={k:('' if k=='Libpath' else []) for k in KEYS}
  self.after={**self.before,'Libpath':'"'+str(self.root)+'"','GlobalLibs':['nom.lib*']}
  self.ini='[PSPICE]\nLIBPATH=$CDSROOT\\tools\\PSpice\\Library\n[PSPICE NETLIST]\nLINE1=.lib "nom.lib"\n[]\nignored=value\n'

 def test_native_checked_global_selection_preserves_unrelated_empty_section_compatibility(self):
  self.assertEqual(decode_selection(self.ini,self.before,self.after,(self.root,)),[str(self.root/'nom.lib')])

 def test_duplicate_relevant_section_or_key_is_ambiguous(self):
  for text in (self.ini+'[PSPICE NETLIST]\nLINE1=.lib "nom.lib"\n',self.ini.replace('LINE1=.lib "nom.lib"','LINE1=.lib "nom.lib"\nline1=.lib "other.lib"')):
   with self.subTest(text=text),self.assertRaises(CadenceError):decode_selection(text,self.before,self.after,(self.root,))

 def test_native_overlay_or_enabled_library_order_mismatch_is_not_silently_dropped(self):
  for before,after in [(self.before,{**self.after,'GlobalLibs':['other.lib*']}),({**self.before,'ProfileLibs':['extra.lib*']},self.after),(self.before,{**self.after,'LocalIncs':['extra.inc*']})]:
   with self.subTest(before=before,after=after),self.assertRaises(CadenceError):decode_selection(self.ini,before,after,(self.root,))

 def test_global_include_and_wildcard_library_need_dedicated_support(self):
  for text in (self.ini.replace('.lib "nom.lib"','.INC "nom.lib"'),self.ini.replace('nom.lib','*.lib')):
   with self.subTest(text=text),self.assertRaises(CadenceError):decode_selection(text,self.before,self.after,(self.root,))

 def test_native_resolved_directory_must_be_in_read_roots(self):
  outside=self.root/'allowed';outside.mkdir()
  with self.assertRaises(CadenceError) as caught:decode_selection(self.ini,self.before,self.after,(outside,))
  self.assertEqual(caught.exception.code,'path_denied')

if __name__=='__main__':unittest.main()
