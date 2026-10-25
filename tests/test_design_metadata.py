import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_design_create import CaptureDesignCreates,COUNT_KEYS,read_document_meta

class DesignMetadataTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        install=self.root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        self.config=Config(install,self.root/'work',(self.root,))
        self.design=self.root/'owned.dsn';self.design.write_bytes(b'owned fixture')
    def meta(self):return {'rootName':'ROOT','schematics':[{'name':'ROOT','rawRefCount':0}],
                          'pages':[{'schematicName':'ROOT','name':'PAGE','counts':{k:0 for k in COUNT_KEYS}}]}
    def test_metadata_shape_and_counts_cannot_turn_invalid_data_into_empty_page(self):
        for key,value in [('rootName','MISSING'),('schematics',[]),('pages',[{'schematicName':'ROOT','name':'PAGE','counts':[]}])]:
            bad=self.meta();bad[key]=value
            def worker(config,script,args,cwd):Path(args[1]).write_text(json.dumps(bad),encoding='utf-8')
            with patch('cadence_mcp.capture_design_create.run_tcl',worker):
                with self.assertRaises(CadenceError) as e:read_document_meta(self.config,self.design,self.root)
            self.assertEqual(e.exception.code,'invalid_worker_result')
        for value in (True,-1,100001):
            bad=self.meta();bad['pages'][0]['counts']['part']=value
            def worker(config,script,args,cwd):Path(args[1]).write_text(json.dumps(bad),encoding='utf-8')
            with patch('cadence_mcp.capture_design_create.run_tcl',worker):
                with self.assertRaises(CadenceError):read_document_meta(self.config,self.design,self.root)
    def test_unverified_unicode_names_are_refused_before_a_plan_is_created(self):
        writer=CaptureDesignCreates(self.config,CaptureService(self.config))
        with self.assertRaises(CadenceError) as e:writer.plan('根图','PAGE')
        self.assertEqual(e.exception.code,'unsupported_design_encoding');self.assertFalse(list(writer.root.glob('plan-*')))
    def test_cancelled_new_design_plan_never_launches_native_creation(self):
        writer=CaptureDesignCreates(self.config,CaptureService(self.config));plan=writer.plan('ROOT','PAGE');writer.cancel(plan['planId'],plan['planDigest'])
        with patch.object(writer,'execute') as native:
            with self.assertRaises(CadenceError):writer.apply(plan['planId'],plan['planDigest'],'cancelled')
            native.assert_not_called()
