import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.page_net_partition import include_net_groups, page_partition, verify_net_groups
def wire(page='P',group='g',name='N'):return {'kind':'wire','schematicName':'S','pageName':page,'group':group,'netName':name,'nativeId':12,'points':[[0,0],[10,0]]}
def pin(ref='R1',group='g',name='N'):return {'kind':'pin','schematicName':'S','pageName':'P','group':group,'netName':name,'reference':ref,'number':'1','name':'A'}
class PagePartitionTests(unittest.TestCase):
 def test_group_ids_and_enumeration_do_not_change_semantic_memberships(self):
  old=[wire(),pin()];new=copy.deepcopy(old)
  for r in new:r['group']='fresh'
  new.reverse();self.assertEqual(page_partition(old),page_partition(new))
 def test_only_selected_native_group_name_can_change(self):
  old=[wire(),pin(),pin('R2','h','OTHER')];new=copy.deepcopy(old)
  for r in new[:2]:r['netName']='GENERATED'
  self.assertEqual(page_partition(old,['S','P',12],'N'),page_partition(new,['S','P',12]))
  new[2]['netName']='WRONG';self.assertNotEqual(page_partition(old,['S','P',12]),page_partition(new,['S','P',12]))
  with self.assertRaises(CadenceError):page_partition(new,['S','P',12],'N')
 def test_partition_split_is_detected_even_with_equal_names(self):
  old=[wire(),pin()];new=copy.deepcopy(old);new[1]['group']='separate'
  self.assertNotEqual(page_partition(old),page_partition(new))
 def test_same_native_group_token_is_separate_on_different_pages(self):
  value=page_partition([wire(),wire('OTHER')]);self.assertEqual(len(value['groups']),2)
 def test_ambiguous_keys_invalid_fields_and_unknown_target_refused(self):
  for rows in ([wire(),wire()], [{**wire(),'nativeId':True}], [{**pin(),'group':None}], [{**wire(),'extra':0}]):
   with self.assertRaises(CadenceError):page_partition(rows)
  with self.assertRaises(CadenceError):page_partition([wire()],['S','P',99])

class DeclaredPageNetGroupTests(unittest.TestCase):
    def setUp(self):
        self.paths = [[[0, 0], [10, 0]], [[5, -5], [5, 5]]]
        self.pins = [
            {"reference": "R1", "pinNumber": "1", "connected": True},
            {"reference": "R2", "pinNumber": "1", "connected": False},
        ]
        self.payload = {"schematicName": "S", "pageName": "P",
                        "expectedWirePaths": self.paths, "expectedConnections": self.pins}
        self.groups = [{"wireIndexes": [0], "pinIndexes": [0]}, {"wireIndexes": [1], "pinIndexes": []}]
        self.rows = [wire(group="native-12"), {**wire(group="native-26"), "points": self.paths[1]},
                     pin("R1", "native-12"), pin("R2", None, "")]

    def test_crossing_and_pin_group_are_checked_by_objects_not_names(self):
        include_net_groups(self.payload, self.groups)
        reversed_wire = {**self.rows[0], "points": self.paths[0][::-1]}
        verify_net_groups([self.rows[3], *self.rows[1:3], reversed_wire, wire(page="OTHER")], self.payload)
        for index, new_group in ((1, "native-12"), (2, "native-26"), (3, "native-26")):
            with self.subTest(index=index), self.assertRaisesRegex(CadenceError, "membership"):
                rows = copy.deepcopy(self.rows)
                rows[index]["group"] = new_group
                verify_net_groups(rows, self.payload)

    def test_missing_duplicate_or_unbound_members_are_refused_at_plan_time(self):
        for groups in (self.groups[:1], [*self.groups, self.groups[0]],
                       [self.groups[0], {"wireIndexes": [1], "pinIndexes": [1]}],
                       [self.groups[0], {"wireIndexes": [True], "pinIndexes": []}]):
            with self.subTest(groups=groups), self.assertRaises(CadenceError):
                include_net_groups(self.payload, groups)

    def test_no_saved_wires_or_connected_pins_can_expect_zero_groups(self):
        self.payload["expectedWirePaths"] = []
        self.payload["expectedConnections"] = self.pins[1:]
        include_net_groups(self.payload, [])
        verify_net_groups(self.rows[3:], self.payload)
        with self.assertRaises(CadenceError):
            verify_net_groups([], self.payload)
