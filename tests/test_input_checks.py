import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_input_checks import PSpiceInputChecks
BANNER='**** 10/25/26 01:00:00 *** PSpice 24.1 *** ID# 0 ****\n**** CIRCUIT DESCRIPTION\n'
class InputCheckTests(unittest.TestCase):
 def service(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'source.cir';source.write_text('* original input\n.PARAM R=1k\nV1 1 0 DC 5\nR1 1 0 {R}\n.OP\n.END\n')
  cfg=Config(install,root/'work',(root,));inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];checks=PSpiceInputChecks(cfg,inputs)
  return source,inputs,sid,checks
 def output(self):
  source,inputs,sid,checks=self.service();plan=checks.plan(sid);d,_,row=checks._load(plan['planId']);p=row['plan']['payload']
  for name,raw in checks.rebased_inputs(d,p).items():(d/name).write_bytes(raw)
  receipt={'entryPoint':'PSpiceSetupAnalysis','caught':0,'setupReturn':'0','finishReturn':'0','cleanupReturn':'0','analysisExecuted':False}
  (d/'receipt.json').write_text(json.dumps(receipt));(d/'result.out').write_text(BANNER,encoding='cp1252');(d/'setup.dat').write_bytes(b'not numerical result')
  return checks,d,p,receipt
 def test_plan_survives_input_session_close_and_binds_originals(self):
  source,inputs,sid,checks=self.service();plan=checks.plan(sid);inputs.close(sid);_,_,row=checks._load(plan['planId']);checks.preflight(row['plan']['payload'])
  self.assertFalse(plan['preview']['analysisWillExecute']);self.assertEqual(plan['preview']['analysisTypes'],['OP'])
 def test_frozen_manifest_prepared_and_original_changes_stop_before_execute(self):
  for member in ('input.cir','originals/source-000.bin','input-manifest.json'):
   source,inputs,sid,checks=self.service();plan=checks.plan(sid);directory=inputs.inputs[sid]['directory'];(directory/member).write_bytes(b'changed')
   with patch.object(checks,'execute') as execute,self.assertRaises(CadenceError) as error:checks.apply(plan['planId'],plan['planDigest'],'bound')
   self.assertEqual(error.exception.code,'target_changed');execute.assert_not_called()
 def test_timeout_and_control_directive_limits_are_checked_at_plan(self):
  source,inputs,sid,checks=self.service()
  for timeout in (True,0,601):
   with self.assertRaises(CadenceError):checks.plan(sid,timeout)
  source.write_text('* unsupported control\n.CONTROL\n.ENDC\n.OP\n.END\n');sid2=inputs.prepare(str(source))['simulationId']
  with self.assertRaises(CadenceError):checks.plan(sid2)
 def test_setup_report_does_not_claim_analysis_or_numerical_acceptance(self):
  checks,d,p,_=self.output();result=checks.verify(d,p,True);manifest=json.loads((d/'input-check-manifest.json').read_text())
  self.assertTrue(result['nativeParserSetupVerified']);self.assertTrue(result['nativeCompletionVerified']);self.assertFalse(result['analysisExecuted']);self.assertFalse(result['solverSuccessVerified']);self.assertFalse(result['numericalAcceptanceVerified']);self.assertEqual(manifest['scope'],'native_parse_setup_only')
  self.assertEqual(manifest['preparedManifestSha256'],p['manifestHash']);self.assertEqual(result['simulationId'],p['simulationId'])
 def test_missing_receipt_never_certified_by_error_free_out(self):
  checks,d,p,_=self.output();(d/'receipt.json').unlink()
  for completed in (True,False):
   with self.assertRaises(CadenceError) as error:checks.verify(d,p,completed)
   self.assertEqual(error.exception.code,'setup_completion_unverified')
 def test_bad_receipt_flags_and_native_out_errors_refused(self):
  checks,d,p,receipt=self.output()
  for key,value in [('caught',True),('entryPoint','other'),('setupReturn','1'),('analysisExecuted',True)]:
   (d/'receipt.json').write_text(json.dumps({**receipt,key:value}))
   with self.assertRaises(CadenceError):checks.verify(d,p,True)
  (d/'receipt.json').write_text(json.dumps(receipt));(d/'result.out').write_text(BANNER+'ERROR -- Convergence problem in DC sweep')
  with self.assertRaises(CadenceError) as error:checks.verify(d,p,True)
  self.assertEqual(error.exception.code,'pspice_nonconvergence')
 def test_job_input_change_is_rejected_even_with_success_receipt(self):
  checks,d,p,_=self.output();(d/'input.cir').write_bytes(b'changed')
  with self.assertRaises(CadenceError) as error:checks.verify(d,p,True)
  self.assertEqual(error.exception.code,'simulation_input_changed')
 def test_reuse_checks_every_input_output_hash(self):
  for member in ('input.cir','receipt.json','result.out','setup.dat'):
   checks,d,p,_=self.output();result=checks.verify(d,p,True)
   with (d/member).open('ab') as stream:stream.write(b' ')
   with self.assertRaises(CadenceError) as error:checks._verified_result(d,{'result':result})
   self.assertEqual(error.exception.code,'target_changed')
 def test_same_entry_hash_does_not_conflate_changed_dependency_closure(self):
  source,inputs,sid,checks=self.service();dependency=source.parent/'model.inc';dependency.write_text('.PARAM EXTRA=1\n')
  source.write_text(source.read_text().replace('.PARAM R=1k','.INC "model.inc"\n.PARAM R=1k'))
  one=inputs.prepare(str(source))['simulationId'];first=checks.plan(one)
  dependency.write_text('.PARAM EXTRA=2\n');two=inputs.prepare(str(source))['simulationId'];second=checks.plan(two)
  self.assertEqual(first['preview']['sourceFingerprint'],second['preview']['sourceFingerprint'])
  self.assertNotEqual(first['preview']['preparedManifestSha256'],second['preview']['preparedManifestSha256'])
