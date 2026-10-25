import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_graphic_line import CaptureGraphicLines,added_line,read_lines
from cadence_mcp.core import Config,CadenceError
from test_connections import design
class GraphicLineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();source=root/'source.dsn';source.write_bytes(b'mock')
        self.config=Config(install,root/'work',(root,));self.capture=CaptureService(self.config)
        ws=self.capture.create_workspace(str(source))
        def reader(config,script,args,cwd):Path(args[1]).write_text(json.dumps(design()))
        with patch('cadence_mcp.capture.run_tcl',reader):self.sid=self.capture.open(ws['workspaceId'])['sessionId']
        self.writer=CaptureGraphicLines(self.config,self.capture)
    def plan(self,start=[0,0],end=[10,0],page='p',lines=None):
        with patch('cadence_mcp.capture_graphic_line.read_lines',return_value=[] if lines is None else lines),patch('cadence_mcp.capture_graphic_line.inventory',return_value=[]):
            return self.writer.plan(self.sid,page,start,end)
    def test_declares_local_and_global_endpoints_preserves_duplicate_lines(self):
        line=added_line([0,0],[10,0]);before=copy.deepcopy(self.capture.sessions[self.sid]['data'])
        p=self.plan(lines=[line]);_,_,row=self.writer._load(p['planId'])
        self.assertEqual(list(row['plan']['payload']['expectedLines'].values()),[2])
        self.assertEqual(before,self.capture.sessions[self.sid]['data'])
    def test_rejects_degenerate_boolean_difference_overflow_and_foreign_page(self):
        for values in [([0,0],[0,0],'p'),([True,0],[10,0],'p'),([-1000000,0],[1000000,0],'p'),([0,0],[10,0],'foreign')]:
            with self.assertRaises(CadenceError):self.plan(*values)
    def test_pending_cancel_and_stale_source_do_not_run_native(self):
        p=self.plan();self.writer.cancel(p['planId'],p['planDigest'])
        with self.assertRaises(CadenceError):self.writer.apply(p['planId'],p['planDigest'],'cancel')
        p=self.plan();self.capture.sessions[self.sid]['design'].write_bytes(b'changed')
        with self.assertRaises(CadenceError):self.writer.apply(p['planId'],p['planDigest'],'stale')
    def test_malformed_native_line_document_is_rejected(self):
        source=self.capture.sessions[self.sid]['design'];directory=source.parent
        for value in [{'lines':[{'start':[0,0]}]}, {'lines':[], 'extra':1}]:
            def reader(config,script,args,cwd):Path(args[1]).write_text(json.dumps(value))
            with patch('cadence_mcp.capture_graphic_line.run_tcl',reader):
                with self.assertRaises(CadenceError):read_lines(self.config,source,directory,'main','page1')
