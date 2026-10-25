import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import test_gui_property as fixture
from cadence_mcp.core import CadenceError
from cadence_mcp.gui_property import GuiPropertyWriter
from cadence_mcp.gui_loader import tcl_string

class TimeoutRecoveryTests(unittest.TestCase):
    setUp=fixture.PropertyWriterTests.setUp
    plan=fixture.PropertyWriterTests.plan
    apply=fixture.PropertyWriterTests.apply

    def uncertain(self):
        self.gui.configs=(self.binding,);self.gui.roots=()
        cfg=json.loads(self.binding.read_text(encoding='utf-8'));cfg['instanceId']='i';self.binding.write_text(json.dumps(cfg),encoding='utf-8')
        preview=self.plan();self.connection.call.side_effect=CadenceError('bridge_unavailable','timeout')
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertFalse(self.gui.sessions)
        return preview

    def test_provably_unstarted_job_retired_without_write(self):
        preview=self.uncertain()
        def rpc(operation,params,**kwargs):
            if operation=='property.outcome':return {'generation':1,'data':{'state':'planned','unchangedGeneration':True,'dirtyState':'clean'}}
            self.assertEqual(operation,'property.abandon');return {'data':{'abandoned':True}}
        fresh=GuiPropertyWriter(self.gui,self.writer.config)
        with patch('cadence_mcp.gui_jobs.RpcConnection.call',side_effect=rpc) as calls:
            result=fresh.recover(preview['plan']['planId'],preview['planDigest'])
            self.assertEqual(result['disposition'],'not_applied');self.assertEqual(calls.call_count,2)
        self.assertEqual(self.design.read_bytes(),b'before')
        self.assertFalse((self.root/'.cadence-mcp-write.lock').exists())
        self.assertEqual(fresh.jobs()['jobs'][0]['state'],'not_applied')

    def test_pending_receipt_with_changed_disk_never_unlocked(self):
        preview=self.uncertain();self.design.write_bytes(b'changed')
        receipt={'data':{'state':'planned','unchangedGeneration':True,'dirtyState':'clean'}}
        with patch('cadence_mcp.gui_jobs.RpcConnection.call',return_value=receipt) as calls:
            with self.assertRaises(CadenceError):self.writer.recover(preview['plan']['planId'],preview['planDigest'])
            self.assertEqual(calls.call_count,1)
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

@unittest.skipUnless(os.environ.get('CADENCE_TEST_TCLSH'),'Native Tcl runtime required')
class LoaderTclTests(unittest.TestCase):
    def test_namespace_load_and_literal_data_never_execute_as_code(self):
        adapter=Path(__file__).resolve().parents[1]/'src/cadence_mcp/adapters/json.tcl'
        value='中文 ADAPTER DESIGN RECEIPT [] $fake ; " {} \\ end\nline'
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'probe.tcl'
            script.write_text('fconfigure stdout -encoding utf-8\nnamespace eval ::caller [list source '+tcl_string(adapter.as_posix())+']\n'
                'set value '+tcl_string(value)+'\nputs [::cmcp::obj value [::cmcp::q $value]]\n',encoding='utf-8')
            result=subprocess.run([os.environ['CADENCE_TEST_TCLSH'],str(script)],capture_output=True,check=True)
            self.assertEqual(json.loads(result.stdout.decode('utf-8'))['value'],value)
