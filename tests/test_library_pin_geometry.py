import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.library_edit import expected_library
from test_library import document

class PinGeometryTests(unittest.TestCase):
    def test_shared_symbol_edit_propagates_but_other_fields_preserved(self):
        data=document();old=copy.deepcopy(data)
        _,expected,affected=expected_library(data,'pin1',hot_spot=[-40,17],visible=False)
        self.assertEqual(len(affected),2)
        for row in expected['pin']:
            self.assertEqual(row['hotSpot'],[-40,17]);self.assertIs(row['visible'],False)
            before=next(p for p in old['pin'] if p['objectId']==row['objectId'])
            self.assertEqual({k:v for k,v in row.items() if k not in ('hotSpot','visible')},
                             {k:v for k,v in before.items() if k not in ('hotSpot','visible')})
        self.assertEqual(data,old)
        expected['pin'][0]['hotSpot'][0]=999
        self.assertEqual(expected['pin'][1]['hotSpot'],[-40,17])

    def test_distinct_symbol_untouched_and_combined_old_fields(self):
        data=document();data['part'][1]['name']='Other'
        _,expected,affected=expected_library(data,'pin1',name='NEW',number='99',pin_type=0,hot_spot=[0,0],visible=False)
        self.assertEqual(len(affected),1);self.assertEqual(expected['pin'][1],data['pin'][1])
        self.assertEqual([expected['pin'][0][k] for k in ('name','number','pinType','hotSpot','visible')],['NEW','99',0,[0,0],False])

    def test_strict_geometry_boundaries_and_boolean(self):
        for hot in ([True,1],[0.0,1],[0],[],[0,1,2],[-1000001,0],(0,1),'0 1'):
            with self.subTest(hot=hot),self.assertRaises(CadenceError):expected_library(document(),'pin1',hot_spot=hot)
        for v in (0,1,'false',[],{}):
            with self.subTest(v=v),self.assertRaises(CadenceError):expected_library(document(),'pin1',visible=v)
        _,expected,_=expected_library(document(),'pin1',hot_spot=[-1000000,1000000])
        self.assertEqual(expected['pin'][0]['hotSpot'],[-1000000,1000000])

    def test_no_change_and_wrong_target(self):
        data=document();data['part'][1]['name']='Other'
        with self.assertRaises(CadenceError) as error:expected_library(data,'pin1',hot_spot=[0,10],visible=True)
        self.assertEqual(error.exception.code,'no_change')
        with self.assertRaises(CadenceError) as error:expected_library(data,'missing',visible=False)
        self.assertEqual(error.exception.code,'object_not_found')
