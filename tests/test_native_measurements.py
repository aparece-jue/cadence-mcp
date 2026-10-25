import copy,json,math,tempfile,unittest
from pathlib import Path
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_measurements import PSpiceMeasurementRuns,parse_measurements,declarations,valid_expectations

def expected(name='peak',field='value',value=2.5):return {'name':name,'field':field,'expected':value,'absoluteTolerance':1e-6,'relativeTolerance':0.0}
class NativeMeasureTests(unittest.TestCase):
 def service(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
  install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'source.cir';source.write_text('* original fixture\nV1 1 0 DC 5\nR1 1 0 1k\n.DC V1 0 5 1\n.MEAS DC peak MAX V(1)\n.END\n')
  cfg=Config(install,root/'work',(root,));inputs=PSpiceInputs(cfg);sid=inputs.prepare(str(source))['simulationId']
  return root,source,inputs,sid,PSpiceMeasurementRuns(cfg,inputs,PSpiceDat(cfg))
 def test_numeric_fields_are_distinct_from_when_trigger_value(self):
  rows=parse_measurements('tau: V(2)= 0.632121 AT 1.0000D-03\npeak: MAX(V(2))= 2.5000E+00 FROM 0 TO 5\n')
  self.assertEqual(rows[0]['fields'],{'value':0.632121,'at':0.001})
  self.assertEqual(rows[1]['fields'],{'value':2.5,'from':0.0,'to':5.0})
  self.assertEqual(parse_measurements('delay: 2.5E-3 FROM 0 TO 3e-3')[0]['fields']['value'],0.0025)
 def test_failed_evaluation_has_no_numeric_field(self):
  row=parse_measurements('gain: Evaluation Failed.')[0]
  self.assertEqual(row['state'],'evaluation_failed');self.assertEqual(row['fields'],{})
 def test_unknown_duplicate_nonfinite_and_ambiguous_results_refused(self):
  for text in ('','\x00','peak: nan','peak: 1E999','peak: 1 AT 2 AT 3','peak: 1 trailing','peak: 1\nPEAK: 2','unexpected format'):
   with self.subTest(text=text),self.assertRaises(CadenceError):parse_measurements(text)
 def test_multiline_declarations_retain_source_and_case(self):
  rows=declarations({'input.cir':'* ignored\n.MEASURE DC Peak\n+ MAX V(2)\n'},'dc')
  self.assertEqual(rows,[{'name':'Peak','analysis':'DC','expression':'MAX V(2)','inputFile':'input.cir'}])
 def test_duplicate_wrong_analysis_empty_and_oversize_declarations_refused(self):
  for text in ('.MEAS DC peak MAX V(2)\n.MEAS DC PEAK MIN V(2)', '.MEAS AC peak MAX V(2)', '.MEAS DC missing','R1 1 0 1k','.MEAS DC peak '+('x'*4097)):
   with self.subTest(text=text),self.assertRaises(CadenceError):declarations({'input.cir':text},'dc')
 def test_expectations_are_finite_named_strict_and_unique(self):
  self.assertTrue(valid_expectations([expected()],{'peak'}))
  self.assertFalse(valid_expectations([expected(),expected()],{'peak'}))
  for key,value in [('name','other'),('field','units'),('expected',True),('expected',math.inf),('absoluteTolerance',0),('relativeTolerance',2)]:
   row=expected();row[key]=value;self.assertFalse(valid_expectations([row],{'peak'}))
 def test_plan_binds_source_and_rejects_multiple_analysis_types(self):
  root,source,inputs,sid,service=self.service();plan=service.plan(sid,'dc',[expected()]);_,_,row=service._load(plan['planId'])
  service.preflight(row['plan']['payload']);self.assertEqual(plan['preview']['acceptanceScope'],'declared_native_measurement_fields_only')
  changed=copy.deepcopy(row['plan']['payload']);changed['expectedSamples']=[{}]
  with self.assertRaises(CadenceError):service.preflight(changed)
  source.write_text(source.read_text().replace('.END','.TRAN 1u 2u\n.END'))
  sid2=inputs.prepare(str(source))['simulationId']
  with self.assertRaises(CadenceError) as error:service.plan(sid2,'dc',[expected()])
  self.assertEqual(error.exception.code,'unsupported_measurement_analyses')
 def test_measurement_identity_and_expected_fields_verified(self):
  root,_,_,sid,service=self.service();plan=service.plan(sid,'dc',[expected()]);d,_,row=service._load(plan['planId']);payload=row['plan']['payload']
  out=d/'input_measure.txt';out.write_text('peak: MAX(V(2))= 2.5 FROM 0 TO 5\n')
  files,evidence=service.extra_artifacts(d,payload);self.assertEqual(files[0]['relativePath'],'input_measure.txt');self.assertEqual(evidence['nativeMeasurementChecks'][0]['observed'],2.5)
  for text,code in [('peak: 3','measurement_expectation_mismatch'),('other: 2.5','measurement_declaration_mismatch'),('peak: Evaluation Failed.','native_measurement_failed')]:
   out.write_text(text)
   with self.assertRaises(CadenceError) as error:service.extra_artifacts(d,payload)
   self.assertEqual(error.exception.code,code)
  out.write_text('peak: 2.5');payload['expectedMeasurements']=[expected(field='at')]
  with self.assertRaises(CadenceError):service.extra_artifacts(d,payload)
 def test_complete_entry_receipt_is_separate_from_stepwise_finish(self):
  root,_,_,sid,service=self.service();plan=service.plan(sid,'dc',[expected()]);d,_,row=service._load(plan['planId'])
  receipt={'entryPoint':'PSpiceDoAnalysis','caught':0,'analysisReturn':'0','cleanupReturn':'0'}
  path=d/'receipt.json';path.write_text(json.dumps(receipt));service.confirm_receipt(d,row['plan']['payload'])
  for key,value in [('entryPoint','doALL'),('caught',True),('analysisReturn','1'),('cleanupReturn','1')]:
   changed={**receipt,key:value};path.write_text(json.dumps(changed))
   with self.assertRaises(CadenceError):service.confirm_receipt(d,row['plan']['payload'])
 def test_complete_output_requires_conclusion_and_statistics(self):
  _,_,_,_,service=self.service();service.confirm_output('JOB CONCLUDED\nJOB STATISTICS SUMMARY',{})
  for text in ('JOB CONCLUDED','JOB STATISTICS SUMMARY','**** Command: FINISH'):
   with self.assertRaises(CadenceError):service.confirm_output(text,{})
