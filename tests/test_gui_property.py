import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cadence_mcp.core import CadenceError, sha256
from cadence_mcp.gui_property import GuiPropertyWriter

DOCUMENT={'schematic':[{'objectId':'s','name':'S'}], 'page':[{'objectId':'p','schematicId':'s','name':'P'}],
          'pin':[{'pageId':'p','reference':'R1','number':'1','net':'N1','connected':True}]}

class PropertyWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.design=self.root/'copy.dsn';self.design.write_bytes(b'before')
        self.binding=self.root/'binding.json'
        self.binding.write_text(json.dumps({'expectedDesign':str(self.design),'sourceFingerprint':sha256(self.design),
            'allowPropertyWrite':True,'writeLeaseId':'private'}),encoding='utf-8')
        (self.root/'write-fixture.json').write_text(json.dumps({'kind':'cadence-mcp-write-fixture-v1',
            'design':str(self.design),'source':str(self.root/'source.dsn')}),encoding='utf-8')
        self.connection=Mock(path=self.binding)
        def call(operation,params,**kwargs):
            if operation=='property.outcome':return {'data':{'state':'saved','unchangedGeneration':True,'dirtyState':'clean'}}
            if operation=='property.plan':return {'data':{'oldExists':False,'oldValue':''}}
            self.design.write_bytes(b'after')
            return {'data':{'saved':True}}
        self.connection.call.side_effect=call
        self.gui=SimpleNamespace(lock=threading.RLock(),sessions={'s':{'access':'write','generation':1,
            'instanceId':'i','connection':self.connection}},instances={'i':{}})
        self.writer=GuiPropertyWriter(self.gui,SimpleNamespace(install_root=self.root/'install'))
        self.writer._inspect=Mock(return_value=DOCUMENT)
        def verifier(config,script,args,cwd):
            Path(args[1]).write_text(json.dumps({'exists':True,'value':'hello'}),encoding='utf-8')
        self.patcher=patch('cadence_mcp.gui_property.run_tcl',side_effect=verifier)
        self.patcher.start();self.addCleanup(self.patcher.stop)

    def plan(self):return self.writer.plan('s','S','P','R1','hello')
    def apply(self,preview,key='once'):
        return self.writer.apply(preview['plan']['planId'],preview['planDigest'],key)

    def test_verified_write_replay_does_not_send_again(self):
        preview=self.plan();result=self.apply(preview)
        self.assertTrue(result['reopened']);self.assertTrue(result['definitionConnectivityMatched'])
        count=self.connection.call.call_count
        self.assertTrue(self.apply(preview)['idempotentReplay'])
        self.assertEqual(self.connection.call.call_count,count)
        self.assertFalse((self.root/'.cadence-mcp-write.lock').exists())
        self.assertNotIn('s',self.gui.sessions)

    def test_digest_mismatch_does_not_write(self):
        preview=self.plan()
        with self.assertRaises(CadenceError):self.writer.apply(preview['plan']['planId'],'wrong','once')
        self.assertEqual(self.design.read_bytes(),b'before')

    def test_changed_file_rejects_plan(self):
        preview=self.plan();self.design.write_bytes(b'external')
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertEqual(self.connection.call.call_count,1)

    def test_ambiguous_transport_is_never_replayed(self):
        preview=self.plan()
        self.connection.call.side_effect=CadenceError('bridge_unavailable','lost after send')
        with self.assertRaises(CadenceError):self.apply(preview)
        count=self.connection.call.call_count
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertEqual(self.connection.call.call_count,count)
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

    def test_connectivity_change_fails_verification_and_retains_lock(self):
        preview=self.plan()
        changed=json.loads(json.dumps(DOCUMENT));changed['pin'][0]['net']='CHANGED'
        self.writer._inspect.return_value=changed
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

    def test_read_session_cannot_plan_write(self):
        self.gui.sessions['s']['access']='read'
        with self.assertRaises(CadenceError):self.plan()
        self.connection.call.assert_not_called()
