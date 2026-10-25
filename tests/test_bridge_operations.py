import json
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
from types import SimpleNamespace
import test_gui_property as fixture
from cadence_mcp.core import CadenceError,sha256
from cadence_mcp.gui_property import GuiPropertyWriter
from cadence_mcp.bridge_diagnostics import diagnose

class ForensicResolutionTests(unittest.TestCase):
    setUp=fixture.PropertyWriterTests.setUp
    plan=fixture.PropertyWriterTests.plan
    apply=fixture.PropertyWriterTests.apply

    def unresolved(self):
        self.gui.configs=(self.binding,);self.gui.roots=()
        cfg=json.loads(self.binding.read_text(encoding='utf-8'));cfg.update(instanceId='i',expectedPid=999999)
        self.binding.write_text(json.dumps(cfg),encoding='utf-8')
        preview=self.plan();self.connection.call.side_effect=CadenceError('bridge_unavailable','lost')
        with self.assertRaises(CadenceError):self.apply(preview)
        self.status=patch('cadence_mcp.gui_job_resolution.process_status',return_value='stopped')
        self.status.start();self.addCleanup(self.status.stop)
        return preview

    def review(self,preview):return self.writer.review(preview['plan']['planId'],preview['planDigest'])
    def resolve(self,preview,review,decision):
        return self.writer.resolve(preview['plan']['planId'],preview['planDigest'],review['review']['reviewId'],review['reviewDigest'],decision)

    def test_saved_artifact_closed_only_after_explicit_review(self):
        preview=self.unresolved();self.design.write_bytes(b'after')
        review=self.review(preview)
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())
        self.assertIn('accept_saved_artifact',review['review']['allowedDecisions'])
        result=self.resolve(preview,review,'accept_saved_artifact')
        self.assertTrue(result['savedArtifactVerified']);self.assertFalse(result['nativeCompletionVerified'])
        self.assertEqual(self.design.read_bytes(),b'after');self.assertFalse((self.root/'.cadence-mcp-write.lock').exists())
        self.assertTrue(self.resolve(preview,review,'accept_saved_artifact')['idempotentReplay'])

    def test_file_change_after_review_keeps_lock(self):
        preview=self.unresolved();review=self.review(preview);self.design.write_bytes(b'external')
        with self.assertRaises(CadenceError):self.resolve(preview,review,'close_unchanged')
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

    def test_running_or_unknown_process_cannot_review(self):
        preview=self.unresolved()
        with patch('cadence_mcp.gui_job_resolution.process_status',return_value='unknown'):
            with self.assertRaises(CadenceError):self.review(preview)

    def test_unverified_changed_file_cannot_be_accepted(self):
        preview=self.unresolved();self.design.write_bytes(b'external')
        with patch.object(self.writer,'_verify',side_effect=CadenceError('reopen_failed','wrong note')):
            review=self.review(preview)
        self.assertEqual(review['review']['allowedDecisions'],[])
        with self.assertRaises(CadenceError):self.resolve(preview,review,'accept_saved_artifact')

    def test_foreign_lock_never_released(self):
        preview=self.unresolved();review=self.review(preview)
        (self.root/'.cadence-mcp-write.lock').write_text(json.dumps({'planId':'another'}),encoding='utf-8')
        with self.assertRaises(CadenceError):self.resolve(preview,review,'close_unchanged')
        self.assertTrue((self.root/'.cadence-mcp-write.lock').exists())

class CacheBoundTests(unittest.TestCase):
    setUp=fixture.PropertyWriterTests.setUp
    plan=fixture.PropertyWriterTests.plan
    apply=fixture.PropertyWriterTests.apply

    def test_more_than_64_successes_keep_hot_cache_bounded(self):
        attached=dict(self.gui.sessions['s'])
        with patch('cadence_mcp.gui_property.RpcConnection.call',return_value={'data':{'released':True}}):
            for index in range(130):
                self.gui.sessions['s']=dict(attached)
                preview=self.plan()
                result=self.apply(preview,key=f'bounded-{index}')
                self.assertTrue(result['reopened'])
                self.assertLessEqual(len(self.writer.plans),64)
        self.assertFalse(list(self.root.glob('verify-copy-*.dsn')))
        self.assertFalse(list(self.root.glob('property-*.json')))

class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.design=self.root/'design.dsn';self.design.write_bytes(b'design')
        self.binding=self.root/'binding.json';self.cfg={'expectedPid':123,'instanceId':'i','expectedDesign':str(self.design),
            'expectedExecutable':str(self.root/'Capture.exe'),'sourceFingerprint':sha256(self.design),'token':'secret-not-returned'}
        self.binding.write_text(json.dumps(self.cfg),encoding='utf-8')
        self.gui=SimpleNamespace(configs=(self.binding,),roots=(),active_operations={})

    def run_diagnosis(self):
        row=diagnose(self.gui)
        self.assertNotIn('secret-not-returned',json.dumps(row))
        return row['bindings'][0]

    def test_process_exit_has_specific_action(self):
        with patch('cadence_mcp.bridge_diagnostics.process_status',return_value='stopped'):
            self.assertEqual(self.run_diagnosis()['condition'],'process_stopped')

    def test_modal_report_does_not_contact_socket(self):
        with patch('cadence_mcp.bridge_diagnostics.process_status',return_value='running'),patch('cadence_mcp.bridge_diagnostics.process_image',return_value=Path(self.cfg['expectedExecutable'])),patch('cadence_mcp.bridge_diagnostics.require_write_ready',side_effect=CadenceError('bridge_busy','modal')),patch('cadence_mcp.bridge_diagnostics.RpcConnection.call') as call:
            self.assertEqual(self.run_diagnosis()['condition'],'modal_or_disabled_window');call.assert_not_called()

    def test_unresolved_lock_takes_priority_over_changed_hash(self):
        (self.root/'.cadence-mcp-write.lock').write_text('{}',encoding='utf-8');self.design.write_bytes(b'changed')
        with patch('cadence_mcp.bridge_diagnostics.process_status',return_value='stopped'):
            self.assertEqual(self.run_diagnosis()['condition'],'unresolved_write')
