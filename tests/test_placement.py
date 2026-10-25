import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.capture_place import validate_pins
from cadence_mcp.capture_wire import expected_definitions
from test_connections import design

class PlacementOracleTests(unittest.TestCase):
    def test_physical_mapping_is_exact_not_logical_count_only(self):
        source=[{'number':'1','name':'A'},{'number':'2','name':'B'}]
        pins=[{'number':n,'name':v,'hotSpot':[x,0],'connected':False,'net':None} for n,v,x in [('1','A',0),('2','B',10)]]
        validate_pins(source,pins)
        for field,value in [('number','3'),('name','wrong')]:
            wrong=copy.deepcopy(pins);wrong[0][field]=value
            with self.assertRaises(CadenceError):validate_pins(source,wrong)
    def test_invalid_hotspot_and_connection_expectation_rejected(self):
        source=[{'number':'1','name':'A'}]
        pin={'number':'1','name':'A','hotSpot':[0,0],'connected':False,'net':None}
        for change in [{'hotSpot':[True,0]},{'hotSpot':[0,1000001]},{'connected':True},{'net':'named'},{'extra':1}]:
            with self.assertRaises(CadenceError):validate_pins(source,[{**pin,**change}])
    def test_duplicate_shared_physical_pin_expectations_are_not_silently_merged(self):
        source=[{'number':'1','name':'A'}]*2
        pin={'number':'1','name':'A','hotSpot':[0,0],'connected':False,'net':None}
        with self.assertRaises(CadenceError):validate_pins(source,[pin,pin])
    def test_existing_page_pins_require_complete_explicit_coverage(self):
        with self.assertRaises(CadenceError):expected_definitions(design(),'p',[])
