import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_cache import query_cache
from test_connections import design
from test_library import document

class CacheQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=root/'source.dsn';source.write_bytes(b'mock DSN')
        self.config=Config(install,root/'work',(root,));self.capture=CaptureService(self.config)
        ws=self.capture.create_workspace(str(source))
        def worker(config,script,args,cwd):Path(args[1]).write_text(json.dumps(design()))
        with patch('cadence_mcp.capture.run_tcl',worker):self.sid=self.capture.open(ws['workspaceId'])['sessionId']
    def worker(self,config,script,args,cwd):
        self.assertEqual(script,'inspect_cache.tcl');Path(args[1]).write_text(json.dumps(document()),encoding='utf-8')
    def test_cache_scope_pagination_and_reuse_are_session_bound(self):
        with patch('cadence_mcp.capture_cache.run_tcl',side_effect=self.worker) as native:
            first=query_cache(self.capture,self.sid,'package',None,None,1)
            second=query_cache(self.capture,self.sid,'package',None,first['nextCursor'],1)
            self.assertEqual(len(first['items'])+len(second['items']),2)
            self.assertEqual(first['scope'],'dsn_cache_device_definitions');self.assertFalse(first['externalSourceLibraryVerified'])
            with self.assertRaises(CadenceError):query_cache(self.capture,self.sid,'pin',None,first['nextCursor'],1)
            self.assertEqual(native.call_count,1)
    def test_package_filter_and_stale_snapshot(self):
        with patch('cadence_mcp.capture_cache.run_tcl',side_effect=self.worker):
            row=query_cache(self.capture,self.sid,'pin','R1');self.assertEqual([p['number'] for p in row['items']],['11'])
            self.assertEqual(query_cache(self.capture,self.sid,'pin','missing')['items'],[])
        self.capture.sessions[self.sid]['design'].write_bytes(b'changed')
        with self.assertRaises(CadenceError):query_cache(self.capture,self.sid,'package')
    def test_invalid_native_document_is_not_cached(self):
        def invalid(config,script,args,cwd):Path(args[1]).write_text('{}')
        with patch('cadence_mcp.capture_cache.run_tcl',side_effect=invalid):
            with self.assertRaises(CadenceError):query_cache(self.capture,self.sid,'package')
        self.assertNotIn('cacheDefinitions',self.capture.sessions[self.sid])
