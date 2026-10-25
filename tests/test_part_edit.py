import copy,unittest
from cadence_mcp.capture_part_edit import declared_pose,geometry_row
from cadence_mcp.core import CadenceError

class PartEditTests(unittest.TestCase):
    def old(self):return {'location':[0,0],'rotationCode':0,'mirrorCode':0,'pins':[{'number':'1','name':'A','hotSpot':[-20,0]},{'number':'2','name':'B','hotSpot':[20,0]}]}
    def test_declared_hotspots_are_not_recomputed_or_mutated(self):
        old=self.old();before=copy.deepcopy(old);pins=[{'number':'2','name':'B','hotSpot':[105,117]},{'number':'1','name':'A','hotSpot':[101,120]}]
        pose=declared_pose(old,[100,100],1,1,pins)
        self.assertEqual(pose['pins'][0]['hotSpot'],[101,120]);self.assertEqual(old,before)
        pins[0]['hotSpot'][0]=0;self.assertEqual(pose['pins'][1]['hotSpot'],[105,117])
    def test_missing_unknown_duplicate_and_boolean_coordinates_rejected(self):
        old=self.old();pins=old['pins']
        for bad in (pins[:1],pins+[pins[0]],[{**pins[0],'number':'3'},pins[1]],[{**pins[0],'hotSpot':[True,0]},pins[1]]):
            with self.assertRaises(CadenceError):declared_pose(old,[0,0],0,0,bad)
        for loc,r,m in (([True,0],0,0),([0,0],True,0),([0,0],0,True),([0,0],4,0),([0,0],0,2)):
            with self.assertRaises(CadenceError):declared_pose(old,loc,r,m,pins)
    def test_saved_ordinal_ids_do_not_define_geometry_identity(self):
        old=self.old();new=copy.deepcopy(old)
        old['pins'][0]['pinId']='before';new['pins'][0]['pinId']='after';new['pins'].reverse()
        self.assertEqual(geometry_row(old),geometry_row(new))
