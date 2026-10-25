import copy,unittest
from cadence_mcp.library_semantics import library_graph
from cadence_mcp.library_edit import expected_library
from cadence_mcp.core import CadenceError
from test_library import document

class LibrarySemanticTests(unittest.TestCase):
    def test_all_ordinal_ids_and_orders_may_change_without_semantic_change(self):
        data=document();changed=copy.deepcopy(data)
        names={row['objectId']:'saved-'+row['objectId'] for rows in changed.values() for row in rows}
        for rows in changed.values():
            rows.reverse()
            for row in rows:
                for field in ('objectId','packageId','deviceId','cellId','partId'):
                    if field in row:row[field]=names[row[field]]
        self.assertEqual(library_graph(data),library_graph(changed))
    def test_pin_mapping_geometry_and_package_changes_are_not_normalized_away(self):
        data=document();before=library_graph(data)
        for kind,field,value in [('package','footprint','different'),('device','position',8),('cell','name','another'),('part','name','alternate'),('pin','number','99'),('pin','pinType',7),('pin','visible',False),('pin','shared',True),('pin','swapId',9),('pin','hotSpot',[1,2])]:
            changed=copy.deepcopy(data);changed[kind][0][field]=value
            self.assertNotEqual(before,library_graph(changed),(kind,field))
    def test_duplicate_semantic_pin_or_package_refused(self):
        data=document();other=copy.deepcopy(data['pin'][0]);other['objectId']='duplicate';data['pin'].append(other)
        with self.assertRaises(CadenceError):library_graph(data)
        data=document();data['package'][1]['name']=data['package'][0]['name'].lower()
        with self.assertRaises(CadenceError):library_graph(data)
    def test_variant_and_device_pin_rows_are_not_collapsed(self):
        data=document();part=copy.deepcopy(data['part'][0]);part.update(objectId='variant',name='Alternative');data['part'].append(part)
        pin=copy.deepcopy(data['pin'][0]);pin.update(objectId='variant-pin',partId='variant');data['pin'].append(pin)
        self.assertEqual(len(library_graph(data)['pin']),3)
    def test_heterogeneous_shared_pad_partial_function_change_refused(self):
        data=document()
        # Two cells of one package share one physical power pad.
        data['package']=data['package'][:1];data['package'][0]['size']=2
        for kind in ('device','cell','part','pin'):
            data[kind][1]['packageId']='p1'
        data['device'][1]['designator']='B';data['cell'][1]['name']='POWER_CELL'
        for p in data['pin']:p.update(name='VCC',number='8',shared=True,pinType=7)
        with self.assertRaises(CadenceError) as error:expected_library(data,'pin1',pin_type=0)
        self.assertEqual(error.exception.code,'shared_pin_function_conflict')
