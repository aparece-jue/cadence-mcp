import unittest
from cadence_mcp.capture_design_create import design_name,empty_definition,COUNT_KEYS
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.core import CadenceError

class DesignCreateTests(unittest.TestCase):
    def test_literal_names_and_path_controls(self):
        for name in ('ROOT','根图一','Power page-1'):self.assertEqual(design_name(name),name)
        for bad in (None,True,'','../escape','root/page','C:\\path','bad\x00name','x.','x ','a;puts x','x\nname','x'*65):
            with self.assertRaises(CadenceError):design_name(bad)
    def test_declared_root_page_distinguished_from_nonempty_design(self):
        data=empty_definition('ROOT','PAGE');before=definition_baseline(data)
        data['part'].append({'objectId':'part','schematicId':'s','pageId':'p','reference':'R1'})
        self.assertNotEqual(definition_baseline(data),before)
        self.assertNotEqual(definition_baseline(empty_definition('OTHER','PAGE')),before)
        self.assertNotEqual(definition_baseline(empty_definition('ROOT','OTHER')),before)
