import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_runs import PSpiceRuns
from cadence_mcp.pspice_output import parse_out
from cadence_mcp.pspice_diagnostics import category,failure_for_output
from cadence_mcp.pspice_failure import inspect_failure
from cadence_mcp.gui_jobs import durable_json
BANNER='**** 10/25/26 01:00:00 *** PSpice 24.1 *** ID# 0 ****\n'
class SolverDiagnosticTests(unittest.TestCase):
 def service(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'source.cir';source.write_text('* independent test\nV1 1 0 DC 5\nR1 1 0 1k\n.DC V1 5 5 1\n.END\n')
  cfg=Config(install,root/'work',(root,));inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];runs=PSpiceRuns(cfg,inputs,PSpiceDat(cfg));plan=runs.plan(sid,'dc')
  return runs,plan
 def failed(self):
  service,key=self.service();d,p,row=service._load(key['planId']);row.update(state='failed',startedAt=1,workerPid=123,error={'code':'pspice_output_error'})
  durable_json(p,row)
  for name,raw in service.rebased_inputs(d,row['plan']['payload']).items():(d/name).write_bytes(raw)
  (d/'result.out').write_text(BANNER+'ERROR -- Convergence problem in DC sweep\n',encoding='cp1252')
  return service,key,d
 def test_double_dash_native_error_is_not_lost(self):
  p=parse_out(BANNER+'ERROR -- Convergence problem in DC sweep\nWARNING(ORPSIM-1): harmless\n')
  self.assertTrue(p['hasErrorDiagnostics']);self.assertEqual(p['diagnostics'][0]['code'],None)
  self.assertEqual(p['diagnosticSummary']['errorCategories'],['nonconvergence']);self.assertEqual(p['diagnosticSummary']['warningCount'],1)
  self.assertEqual(failure_for_output(p).code,'pspice_nonconvergence')
 def test_warning_with_failure_words_does_not_become_error(self):
  p=parse_out(BANNER+'WARNING: convergence failed in previous run\n')
  self.assertFalse(p['hasErrorDiagnostics']);self.assertEqual(p['diagnosticSummary']['errorCategories'],[]);self.assertIsNone(failure_for_output(p))
 def test_missing_model_and_loop_require_matching_native_evidence(self):
  self.assertEqual(category('ORPSIM-15113','Model X used by D1 is undefined'),'missing_model')
  self.assertEqual(category('ORPSIM-15143','Voltage source and/or inductor loop involving V2'),'topology_error')
  self.assertEqual(category('ORPSIM-15113','other text'),'unclassified')
  self.assertEqual(category(None,'Model X is undefined'),'unclassified')
 def test_license_classification_requires_explicit_failure_not_timeout(self):
  for message in ('License checkout failed','Unable to obtain PSpice license','License is not available'):
   p=parse_out(BANNER+'ERROR: '+message+'\n');self.assertEqual(failure_for_output(p).code,'pspice_license_unavailable')
  for message in ('Simulation timed out','License checkout succeeded','License check-out time = 2.0','No convergence error occurred'):
   self.assertEqual(category(None,message),'unclassified')
 def test_time_step_and_generic_error_are_distinct(self):
  self.assertEqual(failure_for_output(parse_out(BANNER+'ERROR -- Time step too small')).code,'pspice_nonconvergence')
  self.assertEqual(failure_for_output(parse_out(BANNER+'ERROR(ORPSIM-1): unknown')).code,'pspice_output_error')
 def test_cancelled_pending_observation_has_no_fabricated_worker_or_output(self):
  service,key=self.service();service.cancel(key['planId'],key['planDigest']);result=inspect_failure(service,key['planId'],key['planDigest'])
  self.assertTrue(result['workerNotStarted']);self.assertFalse(result['workerStoppedVerified']);self.assertEqual(result['observedFiles'],{});self.assertIsNone(result['output']);self.assertFalse(result['solverSuccessVerified'])
 def test_planned_bad_digest_and_unknown_process_refused(self):
  service,key=self.service()
  with self.assertRaises(CadenceError):inspect_failure(service,key['planId'],'0'*64)
  with self.assertRaises(CadenceError):inspect_failure(service,key['planId'],key['planDigest'])
  d,p,row=service._load(key['planId']);row.update(state='failed',startedAt=1,workerPid=None);durable_json(p,row)
  with self.assertRaises(CadenceError) as e:inspect_failure(service,key['planId'],key['planDigest'])
  self.assertEqual(e.exception.code,'process_state_unknown')
 def test_active_or_unknown_original_worker_is_never_read(self):
  service,key,d=self.failed()
  for state in ('running','unknown'):
   with patch('cadence_mcp.pspice_failure.process_status',return_value=state),self.assertRaises(CadenceError) as error:inspect_failure(service,key['planId'],key['planDigest'])
   self.assertEqual(error.exception.code,'process_state_unknown')
 def test_stopped_failure_is_observation_with_bound_hash_and_no_execution(self):
  service,key,d=self.failed();before=sha256(d/'plan.json')
  with patch('cadence_mcp.pspice_failure.process_status',return_value='stopped'),patch.object(service,'execute') as execute:
   result=inspect_failure(service,key['planId'],key['planDigest']);execute.assert_not_called()
  self.assertTrue(result['inputClosureMatchesPlan']);self.assertTrue(result['workerStoppedVerified']);self.assertFalse(result['solverSuccessVerified']);self.assertFalse(result['canReplayMutation'])
  self.assertEqual(result['observedFiles']['result.out']['sha256'],sha256(d/'result.out'));self.assertEqual(before,sha256(d/'plan.json'))
 def test_changed_bytes_during_observation_refuse(self):
  service,key,d=self.failed()
  def mutate(text):
   value=parse_out(text);(d/'result.out').write_text(text+'changed\n',encoding='cp1252');return value
  with patch('cadence_mcp.pspice_failure.process_status',return_value='stopped'),patch('cadence_mcp.pspice_failure.parse_out',side_effect=mutate),self.assertRaises(CadenceError) as error:inspect_failure(service,key['planId'],key['planDigest'])
  self.assertEqual(error.exception.code,'target_changed')
