import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cadence_mcp.core import CadenceError,sha256
from cadence_mcp.editor_wire_host import EditorWireHost
from cadence_mcp.capture_wire import CaptureWireAdds

class EditorWireProofTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.d=self.root/('plan-'+'a'*32);self.d.mkdir()
  self.h={'pid':4321};self.host=EditorWireHost(SimpleNamespace(workspace_root=self.root),None)
  self.good={'jobId':'a'*32,'pid':4321,'saved':True,'hostRestored':True,'invocationReturned':True,'phase':'returned','error':''}
  (self.d/'entered.txt').write_text('a'*32,encoding='utf-8')
 def receipt(self,row):
  (self.d/'native-result.json').write_text(json.dumps(row),encoding='utf-8');return self.host.receipt(self.d,self.h)
 def test_receipt_requires_exact_pid_nonce_and_boolean_types(self):
  self.assertEqual(self.receipt(self.good),self.good)
  for change in ({'jobId':'b'*32},{'pid':True},{'pid':999},{'saved':1},{'hostRestored':'true'}):
   with self.subTest(change=change),self.assertRaises(CadenceError):self.receipt({**self.good,**change})
 def test_missing_restore_proof_never_releases_host_fence(self):
  self.receipt({**self.good,'hostRestored':False})
  with patch('cadence_mcp.editor_wire_host.release') as release,self.assertRaises(CadenceError) as error:self.host.complete(self.d,self.h)
  self.assertEqual(error.exception.code,'host_context_changed');release.assert_not_called()
 def test_failed_host_observation_never_releases_fence(self):
  self.receipt(self.good)
  with patch.object(self.host,'observe',side_effect=CadenceError('host_context_changed','lost')),patch('cadence_mcp.editor_wire_host.release') as release,self.assertRaises(CadenceError):self.host.complete(self.d,self.h)
  release.assert_not_called()
 def test_entry_marker_must_match_even_when_receipt_is_valid(self):
  (self.d/'entered.txt').write_text('b'*32,encoding='utf-8')
  with self.assertRaises(CadenceError):self.receipt(self.good)
 def test_verified_manifest_cannot_be_recreated_or_ignore_tampering(self):
  with self.assertRaises(CadenceError):self.host.manifest(self.d)
  artifact=self.d/'design.dsn';artifact.write_bytes(b'original')
  (self.d/'editor-wire-artifacts.json').write_text(json.dumps({'files':[{'relativePath':'design.dsn','sha256':sha256(artifact)}]}),encoding='utf-8')
  self.host.manifest(self.d);artifact.write_bytes(b'tampered')
  with self.assertRaises(CadenceError):self.host.manifest(self.d)
 def test_editor_arguments_must_be_paired_before_any_native_work(self):
  job=object.__new__(CaptureWireAdds)
  with self.assertRaises(CadenceError) as error:job.plan('s','p',[0,0],[10,0],'NET',[],gui_session_id='gui')
  self.assertEqual(error.exception.code,'invalid_editor_host')
 def test_started_editor_job_cannot_signal_or_kill_host(self):
  job=object.__new__(CaptureWireAdds);job._load=lambda _: (self.d,None,{'digest':'digest','state':'started','plan':{'payload':{'editorHost':{}}}})
  with self.assertRaises(CadenceError) as error:job.cancel('a'*32,'digest')
  self.assertEqual(error.exception.code,'too_late')

if __name__=='__main__':unittest.main()
