import copy,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cadence_mcp.capture_hierarchy_edit import CaptureHierarchyEdits,tree_digest
from cadence_mcp.core import Config,CadenceError
class HierarchyCloneTests(unittest.TestCase):
    def test_tree_baseline_keeps_context_and_all_property_values(self):
        rows=[{'instancePathSegments':['A','U1A'],'properties':[{'name':'Value','value':'1k'},{'name':'ID','value':'123'}]}]
        old=copy.deepcopy(rows);other=copy.deepcopy(rows);other[0]['properties'].reverse();other[0]['occurrenceId']='different'
        self.assertEqual(tree_digest(rows),tree_digest(other));self.assertEqual(rows,old)
        other[0]['properties'][0]['value']='changed';self.assertNotEqual(tree_digest(rows),tree_digest(other))
        other=copy.deepcopy(rows);other[0]['instancePathSegments'][0]='B';self.assertNotEqual(tree_digest(rows),tree_digest(other))
    def setup_writer(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        data={'part':[{'objectId':'b','reference':'B','pageId':'p','schematicId':'s'}],'page':[{'objectId':'p','schematicId':'s','name':'P'}],'schematic':[{'objectId':'s','name':'TOP'},{'objectId':'c','name':'CHILD'}]}
        capture=SimpleNamespace(lock=threading.RLock(),_session=lambda sid:{'data':data})
        return CaptureHierarchyEdits(Config(install,root/'work',(root,)),capture)
    def test_invalid_reference_and_coordinates_never_create_plan(self):
        writer=self.setup_writer()
        for ref,loc in [('B',[0,0]),('bad\nref',[0,0]),('bad ref',[0,0]),('a'*65,[0,0]),('C',[True,0]),('C',[1000001,0])]:
            with self.assertRaises(CadenceError):writer.plan('s','b',ref,loc,[])
        self.assertFalse(list(writer.root.glob('plan-*')))
    def test_placed_external_nested_and_unresolved_implementation_refused(self):
        writer=self.setup_writer()
        scenarios=[('placed',False,[]),('drawn',True,[]),('drawn',False,[{'instancePathSegments':['parent','B']}]),('drawn',False,[{'instancePathSegments':['B'],'properties':[{'name':'Implementation Type','value':'Schematic View'},{'name':'Implementation','value':'MISSING'}]}])]
        for kind,external,tree in scenarios:
            units={'b':{'kind':kind,'isExternalDesignPart':external}}
            with patch('cadence_mcp.capture_hierarchy_edit.read_units',return_value=units),patch('cadence_mcp.capture_hierarchy_edit.tree_rows',return_value=tree):
                with self.assertRaises(CadenceError):writer.plan('s','b','C',[0,0],[])
        self.assertFalse(list(writer.root.glob('plan-*')))
