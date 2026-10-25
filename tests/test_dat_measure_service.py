import unittest
from unittest.mock import patch
import test_pspice_dat as dat_tests
from cadence_mcp.core import CadenceError
class ServiceMeasureTests(unittest.TestCase):
    setUp=dat_tests.DatTests.setUp
    def test_measurement_retains_import_provenance_and_rejects_bad_requests_before_native(self):
        def worker(directory,mode,block=0,trace=''):
            if mode=='headers':return dat_tests.document()
            csv='1,0,2,0,3,0' if trace=='Frequency' else '3,4,0,-1,-3,-4'
            return {'block':block,'trace':trace,'rows':3,'valuesCSV':csv}
        with patch.object(self.service,'_worker',side_effect=worker) as native:
            ident=self.service.open(str(self.source))['datId']
            for args in [('summary','real',None,1,'either'),('value_at','real',True,None,'either')]:
                with self.assertRaises(CadenceError):self.service.measure(ident,0,'Gain',*args)
            with self.assertRaises(CadenceError):self.service.measure(ident,0,'MISSING')
            self.assertEqual(native.call_count,1)
            value=self.service.measure(ident,0,'V(out)','value_at','magnitude',1,None,'either')
            self.assertEqual(value['value'],5);self.assertFalse(value['jobAssociationVerified']);self.assertEqual(value['provenance'],'imported_file')
            self.assertIsNone(value['producedByPlan']);self.assertIsNone(value['designPassed'])
