import copy,unittest
from cadence_mcp.library_edit import expected_pin_start
from cadence_mcp.core import CadenceError

def graph():
    return {'metadata':{'symbols':[
        {'scope':['P','A',0,'CELL','NORMAL'],'pinStarts':[{'position':0,'start':[-10,0]},{'position':1,'start':[10,0]}],'orderedVectors':[['line',[-10,-5],[10,5]]]},
        {'scope':['P','B',1,'CELL','NORMAL'],'pinStarts':[{'position':0,'start':[-10,0]},{'position':1,'start':[10,0]}],'orderedVectors':[['line',[-10,-5],[10,5]]]},
        {'scope':['P','A',0,'CELL','CONVERT'],'pinStarts':[{'position':0,'start':[0,-10]}],'orderedVectors':[]},
        {'scope':['OTHER','A',0,'OTHER_CELL','NORMAL'],'pinStarts':[{'position':0,'start':[9,9]}],'orderedVectors':[]}]}}

class PinStartTests(unittest.TestCase):
    def test_all_shared_rows_change_and_other_views_preserved(self):
        before=graph();original=copy.deepcopy(before);expected,changes,old=expected_pin_start(before,'CELL','NORMAL',0,[-7,0])
        self.assertEqual(old,[-10,0]);self.assertEqual(len(changes),2);self.assertEqual(before,original)
        for i in (0,1):
            self.assertEqual(expected['metadata']['symbols'][i]['pinStarts'][0]['start'],[-7,0])
            self.assertEqual(expected['metadata']['symbols'][i]['pinStarts'][1],original['metadata']['symbols'][i]['pinStarts'][1])
            self.assertEqual(expected['metadata']['symbols'][i]['orderedVectors'],original['metadata']['symbols'][i]['orderedVectors'])
        self.assertEqual(expected['metadata']['symbols'][2:],original['metadata']['symbols'][2:])
        expected['metadata']['symbols'][0]['pinStarts'][0]['start'][0]=99
        self.assertEqual(expected['metadata']['symbols'][1]['pinStarts'][0]['start'],[-7,0])

    def test_mismatched_shared_starts_and_missing_pin_refused(self):
        for mode in ('mismatch','missing','duplicate'):
            g=graph();pin=g['metadata']['symbols'][1]['pinStarts']
            if mode=='mismatch':pin[0]['start']=[-11,0]
            elif mode=='missing':pin.pop(0)
            else:pin.append(copy.deepcopy(pin[0]))
            with self.subTest(mode=mode),self.assertRaises(CadenceError):expected_pin_start(g,'CELL','NORMAL',0,[0,0])

    def test_bad_coordinates_and_unknown_scope(self):
        for point in ([True,0],[1.0,0],[1000001,0],(1,2),[0],[0,1,2],None):
            with self.subTest(point=point),self.assertRaises(CadenceError):expected_pin_start(graph(),'CELL','NORMAL',0,point)
        with self.assertRaises(CadenceError):expected_pin_start(graph(),'missing','NORMAL',0,[0,0])

    def test_no_change_retains_graph_and_old_start(self):
        g=graph();e,changes,old=expected_pin_start(g,'CELL','NORMAL',0,[-10,0])
        self.assertEqual(g,e);self.assertEqual(changes,[]);self.assertEqual(old,[-10,0])

    def test_affected_row_budget(self):
        g=graph();row=g['metadata']['symbols'][0]
        g['metadata']['symbols']=[{**copy.deepcopy(row),'scope':['P',str(i),i,'CELL','NORMAL']} for i in range(65)]
        with self.assertRaises(CadenceError) as error:expected_pin_start(g,'CELL','NORMAL',0,[0,0])
        self.assertEqual(error.exception.code,'affected_limit')
