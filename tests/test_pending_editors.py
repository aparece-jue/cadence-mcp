"""Host invariants for editors whose native acceptance remains pending."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_pages import CapturePages
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.library_edit import expected_library,LibraryPinEdits
from cadence_mcp.library import LibraryService
from test_connections import design
from test_library import document


class LibraryEditPlanningTests(unittest.TestCase):
    def test_symbol_sharing_is_explicit_but_number_is_device_local(self):
        data=document()
        old,expected,affected=expected_library(data,'pin1','Renamed','99',0)
        self.assertEqual(len(affected),2)
        self.assertEqual([p['name'] for p in expected['pin']],['Renamed','Renamed'])
        self.assertEqual([p['pinType'] for p in expected['pin']],[0,0])
        self.assertEqual([p['number'] for p in expected['pin']],['99','12'])
        self.assertEqual(data['pin'][0]['name'],'端子')
        self.assertEqual(expected['package'],data['package'])

    def test_duplicate_pad_and_shared_pad_renumber_rejected(self):
        data=document();other=copy.deepcopy(data['pin'][0]);other.update(objectId='other',number='99',position=1)
        data['pin'].append(other)
        with self.assertRaises(CadenceError):expected_library(data,'pin1',number='99')
        data['pin'][0]['shared']=True
        with self.assertRaises(CadenceError):expected_library(data,'pin1',number='100')

    def test_noop_controls_boolean_type_and_missing_pin_rejected(self):
        for args in [{'name':'端子'},{'name':'bad\x00name'},{'number':'A;puts bad'},{'pin_type':True},{'pin_type':8},{}]:
            with self.assertRaises(CadenceError):expected_library(document(),'pin1',**args)
        with self.assertRaises(CadenceError):expected_library(document(),'missing',name='x')

    def test_different_cell_symbol_is_not_renamed(self):
        data=document();data['cell'][1]['name']='another'
        _,expected,affected=expected_library(data,'pin1',name='New')
        self.assertEqual(len(affected),1)
        self.assertEqual(expected['pin'][1],data['pin'][1])


class PagePlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);install=self.root/'install'
        (install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=self.root/'source.dsn';source.write_bytes(b'mock DSN')
        self.config=Config(install,self.root/'work',(self.root,));self.service=CaptureService(self.config)
        ws=self.service.create_workspace(str(source))
        def read(config,script,args,cwd):Path(args[1]).write_text(json.dumps(design()),encoding='utf-8')
        with patch('cadence_mcp.capture.run_tcl',read):self.sid=self.service.open(ws['workspaceId'])['sessionId']
        self.editor=CapturePages(self.config,self.service)

    def payload(self,plan):return self.editor._load(plan['planId'])[2]['plan']['payload']

    def test_create_adds_only_page_to_explicit_definition_expectation(self):
        plan=self.editor.plan(self.sid,'create','s',None,'NEW_PAGE')
        expected=design();expected['page'].append({'objectId':'any-new-id','name':'NEW_PAGE','schematicId':'s'})
        self.assertEqual(self.payload(plan)['expectedDefinitionDigest'],definition_baseline(expected))
        self.assertEqual(len(self.service.sessions[self.sid]['data']['page']),1)

    def test_rename_changes_qualified_names_and_preserves_pin_nets(self):
        plan=self.editor.plan(self.sid,'rename','s','p','RENAMED')
        expected=design();expected['page'][0]['name']='RENAMED'
        self.assertEqual(self.payload(plan)['expectedDefinitionDigest'],definition_baseline(expected))
        expected['pin'][0]['net']='WRONG'
        self.assertNotEqual(self.payload(plan)['expectedDefinitionDigest'],definition_baseline(expected))

    def test_conflicts_unknown_scope_and_invalid_create_target(self):
        for args in [('create','s',None,'PAGE1'),('rename','s','bad','New'),('create','bad',None,'New'),('create','s','p','New')]:
            with self.assertRaises(CadenceError):self.editor.plan(self.sid,*args)

    def test_path_controls_and_unimplemented_delete_refused(self):
        for op,name in [('delete','New'),('create','../escape'),('create','bad\x00name'),('create','name.'),('create','a/b')]:
            with self.assertRaises(CadenceError):self.editor.plan(self.sid,op,'s',None,name)

    def test_source_changed_after_plan_refuses_execution(self):
        plan=self.editor.plan(self.sid,'create','s',None,'New');payload=self.payload(plan)
        Path(payload['sourceDesign']).write_bytes(b'changed')
        with self.assertRaises(CadenceError):self.editor.preflight(payload)
