import copy,unittest
from cadence_mcp.capture_references import reference_map
from cadence_mcp.core import CadenceError

def definition():
    return {'schematic':[{'objectId':'s','name':'ROOT'}],'page':[{'objectId':'p','schematicId':'s','name':'MAIN'}],
            'part':[{'objectId':k,'pageId':'p','schematicId':'s','reference':ref} for k,ref in [('a','R101'),('b','R102')]],
            'pin':[{'objectId':k+n,'partId':k,'pageId':'p','schematicId':'s','reference':ref,'number':n,'name':n,'connected':n=='2','net':'SIGNAL' if n=='2' else ''} for k,ref in [('a','R101'),('b','R102')] for n in ('1','2')]}

class ReferenceMapTests(unittest.TestCase):
    def test_swap_keeps_physical_pin_bindings_and_geometry_locator(self):
        data=definition();before=copy.deepcopy(data)
        selected,temp,expected=reference_map(data,[{'partId':'a','newReference':'R102'},{'partId':'b','newReference':'R101'}])
        self.assertEqual(expected['pin'][0]['reference'],'R102');self.assertEqual(expected['pin'][2]['reference'],'R101')
        self.assertEqual([(p['number'],p['net'],p['connected']) for p in expected['pin']],[(p['number'],p['net'],p['connected']) for p in data['pin']])
        self.assertEqual(data,before);self.assertEqual(len(set(temp.values())),2);self.assertFalse(set(temp.values())&{'R101','R102'})
    def test_unmapped_conflict_duplicate_parts_and_destinations_refused(self):
        for mapping in ([{'partId':'a','newReference':'R102'}],[{'partId':'a','newReference':'R201'},{'partId':'a','newReference':'R202'}],[{'partId':'a','newReference':'R201'},{'partId':'b','newReference':'r201'}]):
            with self.assertRaises(CadenceError):reference_map(definition(),mapping)
    def test_prefix_unnumbered_and_controls_refused(self):
        for ref in ('U201','R?','R0','R01','R1;puts x','../R1','R1000000000','R1\x00'):
            with self.assertRaises(CadenceError):reference_map(definition(),[{'partId':'a','newReference':ref}])
    def test_existing_temporary_number_is_skipped(self):
        data=definition();data['part'].append({'objectId':'c','pageId':'p','schematicId':'s','reference':'R900000000'})
        _,temp,_=reference_map(data,[{'partId':'a','newReference':'R201'}]);self.assertEqual(temp['a'],'R900000001')
    def test_repeated_reference_requires_unit_aware_operation(self):
        data=definition();data['part'][1]['reference']='R101'
        with self.assertRaises(CadenceError) as error:reference_map(data,[{'partId':'a','newReference':'R201'}])
        self.assertEqual(error.exception.code,'ambiguous_reference')
    def test_unknown_empty_noop_and_extra_fields_refused(self):
        for rows in ([],[{'partId':'missing','newReference':'R201'}],[{'partId':'a','newReference':'R101'}],[{'partId':'a','newReference':'R201','eval':'x'}]):
            with self.assertRaises(CadenceError):reference_map(definition(),rows)
