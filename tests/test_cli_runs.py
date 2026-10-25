import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_cli_runs import PSpiceCliRuns
BANNER='**** 10/25/26 01:00:00 *** PSpice 24.1 *** ID# 0 ****\nJOB CONCLUDED\nJOB STATISTICS SUMMARY\n'
class CliRunTests(unittest.TestCase):
 def service(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'input.cir';source.write_text('* original CLI test\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE\n.END\n')
  cfg=Config(install,root/'work',(root,));inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId'];cli=PSpiceCliRuns(cfg,inputs,PSpiceDat(cfg));return source,inputs,sid,cli
 def output(self):
  source,inputs,sid,cli=self.service();point={'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0};plan=cli.plan(sid,'dc',[point]);d,_,row=cli._load(plan['planId']);p=row['plan']['payload']
  def native(cmd,directory,env,timeout,cancel=None,on_started=None):
   (directory/'input.out').write_text(BANNER,encoding='cp1252');(directory/'input.dat').write_bytes(b'owned synthetic test bytes')
   return {'state':'exited','returnCode':0,'remainingOwnedProcesses':0,'rootExitSignalConfirmed':True,'observedProcessExitSignalsConfirmed':True}
  with patch('cadence_mcp.pspice_runs.run_owned_process',side_effect=native):process=cli.execute(d,p,None,lambda pid:None)
  return cli,d,p,process
 def test_fixed_installed_cli_command_only_r_flag(self):
  source,inputs,sid,cli=self.service();p=cli.plan(sid,'dc');d,_,row=cli._load(p['planId']);cmd=cli.native_command(d,row['plan']['payload']);self.assertEqual(Path(cmd[0]).name,'psp_cmd.exe');self.assertEqual(cmd[1:],['/r',str(d/'input.cir')])
 def test_cli_rejects_multiple_analysis_types_before_start(self):
  source,inputs,sid,cli=self.service();source.write_text(source.read_text().replace('.END','.TRAN 1u 2u\n.END'));sid=inputs.prepare(str(source))['simulationId']
  with self.assertRaises(CadenceError) as error:cli.plan(sid,'dc')
  self.assertEqual(error.exception.code,'unsupported_cli_analyses')
 def test_native_output_copy_and_owned_completion_receipt(self):
  cli,d,p,process=self.output();self.assertEqual((d/'input.out').read_bytes(),(d/'result.out').read_bytes());self.assertEqual((d/'input.dat').read_bytes(),(d/'result.dat').read_bytes());cli.confirm_receipt(d,p)
  self.assertFalse((d/'receipt.json').exists());self.assertEqual(json.loads((d/'cli-receipt.json').read_text())['command'],['psp_cmd.exe','/r','input.cir'])
 def test_preexisting_cli_output_is_not_overwritten_or_used(self):
  source,inputs,sid,cli=self.service();plan=cli.plan(sid,'dc');d,_,row=cli._load(plan['planId']);(d/'input.out').write_bytes(b'old output')
  with patch('cadence_mcp.pspice_runs.run_owned_process') as worker,self.assertRaises(CadenceError) as error:cli.execute(d,row['plan']['payload'],None,lambda pid:None)
  self.assertEqual(error.exception.code,'preexisting_cli_output');worker.assert_not_called();self.assertEqual((d/'input.out').read_bytes(),b'old output');self.assertFalse((d/'input.cir').exists())
 def test_wrong_receipt_and_changed_job_input_refused(self):
  cli,d,p,_=self.output();path=d/'cli-receipt.json';receipt=json.loads(path.read_text())
  for key,value in [('returnCode',False),('returnCode',1),('rootExitSignalConfirmed',False),('remainingOwnedProcesses',True),('command',['pspice.exe','/r','input.cir'])]:
   path.write_text(json.dumps({**receipt,key:value}))
   with self.assertRaises(CadenceError):cli.confirm_receipt(d,p)
  path.write_text(json.dumps(receipt));(d/'input.cir').write_bytes(b'changed')
  with self.assertRaises(CadenceError):cli.confirm_receipt(d,p)
 def test_raw_canonical_bytes_must_match(self):
  cli,d,p,_=self.output();(d/'input.dat').write_bytes(b'changed raw native output')
  with self.assertRaises(CadenceError):cli.extra_artifacts(d,p)
 def test_cli_requires_completion_markers_not_engine_finish_command(self):
  source,inputs,sid,cli=self.service();cli.confirm_output(BANNER,{})
  with self.assertRaises(CadenceError):cli.confirm_output('**** Command: FINISH\nJOB STATISTICS SUMMARY',{})
 def test_unknown_nonzero_exit_is_not_invented_license_failure(self):
  source,inputs,sid,cli=self.service();plan=cli.plan(sid,'dc');d,_,row=cli._load(plan['planId']);self.assertEqual(cli.worker_error(d,row['plan']['payload'],{'returnCode':2}).code,'pspice_cli_failed')
 def test_cli_manifest_scope_and_backend_are_not_measurement_or_engine(self):
  cli,d,p,_=self.output();reader=MagicMock();reader.open.return_value={'datId':'test'};reader.query.return_value={'items':[{'analysisName':'DC Sweep','analogReadSupported':True,'rowCount':1,'index':0,'axis':'V1','dataTypeCode':0}]};reader.samples.return_value={'items':[{'real':2.5,'imaginary':None}]}
  with patch('cadence_mcp.pspice_runs.PSpiceDat',return_value=reader):result=cli.verify(d,p,True)
  manifest=json.loads((d/'run-artifacts.json').read_text());self.assertEqual(manifest['backend'],'official_psp_cmd_r');self.assertEqual(manifest['scope'],'declared_trace_rows_only');self.assertTrue(manifest['nativeOutputIdentityVerified']);self.assertNotIn('cli_backend',result['notChecked']);self.assertTrue(result['numericalAcceptanceVerified'])
