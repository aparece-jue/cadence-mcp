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
    def test_color_requires_complete_stroke_and_known_palette(self):
        for style,width,color in [(1,1,True),(1,1,0),(1,1,49),(None,None,8),(1,None,8)]:
            with self.assertRaises(CadenceError):self.writer.plan(self.sid,'p',[0,0],[10,0],style,width,color)
    def test_color_plan_preserves_both_native_levels_and_legacy_command(self):
        old=added_line([0,0],[10,0],dict(lineStyle=1,lineWidth=1,lineColor=8,definitionColor=8))
        with patch('cadence_mcp.capture_graphic_line.read_lines',return_value=[old]),patch('cadence_mcp.capture_graphic_line.inventory',return_value=[]):
            plan=self.writer.plan(self.sid,'p',[0,0],[10,0],1,1,8)
        directory,_,row=self.writer._load(plan['planId']);payload=row['plan']['payload']
        self.assertEqual(list(payload['expectedLines'].values()),[2])
        self.assertEqual(self.writer.native_command(directory,payload)[-3:],['1','1','8'])
        legacy={k:v for k,v in payload.items() if k not in ('lineStyle','lineWidth','lineColor')}
        self.assertEqual(self.writer.native_command(directory,legacy)[-1],'add')
    def test_color_reader_rejects_invalid_and_boolean_palette_values(self):
        source=self.capture.sessions[self.sid]['design'];directory=source.parent
        for color in (True,0,49):
            row=added_line([0,0],[10,0],dict(lineStyle=1,lineWidth=1,lineColor=color,definitionColor=8))
            def reader(config,script,args,cwd):Path(args[1]).write_text(json.dumps({'lines':[row]}))
            with patch('cadence_mcp.capture_graphic_line.run_tcl',reader),self.assertRaises(CadenceError):
                read_lines(self.config,source,directory,'main','page1',True,True)
