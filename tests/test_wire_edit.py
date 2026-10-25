import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_wire_edit import CaptureWireEdits,edit_objects
from cadence_mcp.core import Config,CadenceError
from test_connections import design

def objects():return [
    {'kind':'wire','objectId':'w','pageId':'p','attributes':{'net':'INPUT','points':[[0,0],[10,0]]}},
    {'kind':'alias','objectId':'a','pageId':'p','attributes':{'wireId':'w','name':'INPUT','location':[0,0]}}]
def spec():return [{'schematicName':'main','pageName':'page1','reference':'U1','pinNumber':n,'connected':False,'net':None} for n in ('1','2')]

class AliasEditTests(unittest.TestCase):
    def test_deletion_requires_explicit_alias_ack_and_removes_both_objects(self):
        data=objects()
        with self.assertRaises(CadenceError):edit_objects(data,data[0],'delete',None,None,[],False)
        result,aliases=edit_objects(data,data[0],'delete',None,None,[],True)
        self.assertEqual(result,[]);self.assertEqual(aliases[0]['name'],'INPUT');self.assertEqual(len(data),2)
    def test_all_aliases_must_be_declared_and_on_new_segment(self):
        data=objects()
        for aliases in [[],[{'aliasId':'outside','location':[0,10]}],[{'aliasId':'a','location':[0,11]}]]:
            with self.assertRaises(CadenceError):edit_objects(data,data[0],'set_endpoints',[0,10],[10,10],aliases,False)
        result,_=edit_objects(data,data[0],'set_endpoints',[0,10],[10,10],[{'aliasId':'a','location':[0,10]}],False)
        self.assertEqual(result[1]['attributes']['location'],[0,10]);self.assertEqual(data[1]['attributes']['location'],[0,0])
    def test_ambiguous_alias_semantics_are_rejected(self):
        data=objects();data.append({**copy.deepcopy(data[1]),'objectId':'a2'})
        with self.assertRaises(CadenceError):edit_objects(data,data[0],'delete',None,None,[],True)

class WireEditPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=root/'source.dsn';source.write_bytes(b'mock DSN');config=Config(install,root/'work',(root,))
        self.capture=CaptureService(config);ws=self.capture.create_workspace(str(source))
        def reader(config,script,args,cwd):Path(args[1]).write_text(json.dumps(design()))
        with patch('cadence_mcp.capture.run_tcl',reader):self.sid=self.capture.open(ws['workspaceId'])['sessionId']
        self.writer=CaptureWireEdits(config,self.capture)
    def plan(self,**kwargs):
        args={'sid':self.sid,'wire_id':'w','operation':'set_endpoints','expectations':spec(),'start':[0,10],'end':[10,10],'alias_moves':[{'aliasId':'a','location':[0,10]}]};args.update(kwargs)
        with patch('cadence_mcp.capture_wire_edit.inventory',return_value=objects()):return self.writer.plan(**args)
    def test_plan_does_not_modify_source_and_declares_alias_and_paths(self):
        before=copy.deepcopy(self.capture.sessions[self.sid]['data']);p=self.plan()
        self.assertEqual(before,self.capture.sessions[self.sid]['data']);self.assertEqual(p['preview']['aliases'][0]['oldLocation'],[0,0])
        self.assertEqual(p['preview']['expectedWirePaths'],[[[0,10],[10,10]]])
    def test_duplicate_geometry_net_target_is_ambiguous(self):
        data=objects();data.append({**copy.deepcopy(data[0]),'objectId':'second'})
        with patch('cadence_mcp.capture_wire_edit.inventory',return_value=data):
            with self.assertRaises(CadenceError):self.writer.plan(self.sid,'w','delete',spec(),remove_aliases=True)
    def test_extra_geometry_and_incomplete_pin_oracles_rejected(self):
        for changes in [{'expectations':spec()[:1]},{'expected_paths':[[[0,10],[11,10]]]},{'start':[True,0]},{'operation':'eval'}]:
            with self.assertRaises(CadenceError):self.plan(**changes)
    def test_stale_source_and_pending_cancel_do_not_execute(self):
        p=self.plan();self.writer.cancel(p['planId'],p['planDigest'])
        with self.assertRaises(CadenceError):self.writer.apply(p['planId'],p['planDigest'],'cancel-key')
        p=self.plan();self.capture.sessions[self.sid]['design'].write_bytes(b'changed')
        with self.assertRaises(CadenceError):self.writer.apply(p['planId'],p['planDigest'],'stale-key')
    def test_semantic_locator_is_serialized_not_native_pointer_or_ordinal(self):
        p=self.plan();directory,_,row=self.writer._load(p['planId']);args=self.writer.native_command(directory,row['plan']['payload'])
        self.assertEqual(len(args)-2,21);self.assertIn('INPUT',args);self.assertNotIn('w',args)
