import json
import unittest
from unittest.mock import patch

import test_gui_property as fixture
from cadence_mcp.core import CadenceError
from cadence_mcp.gui_property import GuiPropertyWriter
from cadence_mcp.gui_jobs import acquire_guard,durable_json


class JobRecoveryTests(unittest.TestCase):
    setUp=fixture.PropertyWriterTests.setUp
    plan=fixture.PropertyWriterTests.plan
    apply=fixture.PropertyWriterTests.apply

    def setup_registry(self):
        self.gui.configs=(self.binding,);self.gui.roots=()
        config=json.loads(self.binding.read_text(encoding='utf-8'));config['instanceId']='i'
        self.binding.write_text(json.dumps(config),encoding='utf-8')

    def uncertain(self):
        self.setup_registry();preview=self.plan()
        self.connection.call.side_effect=CadenceError('bridge_unavailable','Injected receipt loss')
        with self.assertRaises(CadenceError):self.apply(preview)
        return preview

    def test_cancel_survives_new_writer_and_prevents_apply(self):
        self.setup_registry();preview=self.plan();p=preview['plan']['planId']
        fresh=GuiPropertyWriter(self.gui,self.writer.config)
        self.assertTrue(fresh.cancel(p,preview['planDigest'])['cancelled'])
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertEqual(self.connection.call.call_count,1)
        self.assertEqual(fresh.jobs()['jobs'][0]['state'],'cancelled')

    def test_started_write_cannot_cancel(self):
        preview=self.uncertain()
        with self.assertRaises(CadenceError):self.writer.cancel(preview['plan']['planId'],preview['planDigest'])
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

    def test_recover_from_disk_without_sessions_or_memory_plans(self):
        preview=self.uncertain();self.design.write_bytes(b'after')
        self.gui.sessions.clear()
        fresh=GuiPropertyWriter(self.gui,self.writer.config)
        fresh._inspect=self.writer._inspect
        receipt={'generation':4,'data':{'state':'saved','unchangedGeneration':True,'dirtyState':'clean'}}
        with patch('cadence_mcp.gui_jobs.RpcConnection.call',return_value=receipt) as rpc:
            result=fresh.recover(preview['plan']['planId'],preview['planDigest'])
            self.assertTrue(result['recovered']);self.assertEqual(rpc.call_count,2)
            self.assertTrue(all(c.args[0]=='property.outcome' for c in rpc.call_args_list))
        self.assertFalse((self.root/'.cadence-mcp-write.lock').exists())
        self.assertEqual(fresh.jobs()['jobs'][0]['state'],'verified')

    def test_changed_native_context_keeps_lock(self):
        preview=self.uncertain()
        receipt={'generation':5,'data':{'state':'saved','unchangedGeneration':False,'dirtyState':'clean'}}
        with patch('cadence_mcp.gui_jobs.RpcConnection.call',return_value=receipt):
            with self.assertRaises(CadenceError):self.writer.recover(preview['plan']['planId'],preview['planDigest'])
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

    def test_live_apply_guard_blocks_recovery(self):
        preview=self.uncertain();guard=acquire_guard(self.root)
        try:
            with self.assertRaises(CadenceError):self.writer.recover(preview['plan']['planId'],preview['planDigest'])
        finally:guard.close()

    def test_cancel_during_preflight_rechecked_under_lock(self):
        self.setup_registry();preview=self.plan();p=self.root/f"plan-{preview['plan']['planId']}.json"
        def race(directory):
            row=json.loads(p.read_text(encoding='utf-8'));row['state']='cancelled';durable_json(p,row)
            return acquire_guard(directory)
        with patch('cadence_mcp.gui_property.acquire_guard',side_effect=race):
            with self.assertRaises(CadenceError):self.apply(preview)
        self.assertEqual(self.connection.call.call_count,1)
        self.assertEqual(self.design.read_bytes(),b'before')

    def test_job_id_cannot_escape_private_directory(self):
        self.setup_registry()
        with self.assertRaises(CadenceError):self.writer.cancel('../../binding','x')

    def test_modal_preflight_rejects_without_start_journal(self):
        preview=self.plan()
        self.connection.ready_for_write.side_effect=CadenceError('bridge_busy','modal')
        with self.assertRaises(CadenceError):self.apply(preview)
        self.assertFalse((self.root/'.cadence-mcp-write.lock').exists())
        self.assertFalse([p for p in self.root.glob('write-*.json') if p.name!='write-fixture.json'])
