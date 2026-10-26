import tempfile,unittest,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_runs import PSpiceRuns,execution_closure,execution_preflight
from cadence_mcp.pspice_dat import PSpiceDat
class ModelUseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);r=Path(self.tmp.name);self.src=r/'source';self.src.mkdir();i=r/'install';(i/'tcltk/bin').mkdir(parents=True);(i/'tcltk/bin/tclsh.exe').touch();self.cfg=Config(i,r/'work',(self.src,));self.inputs=PSpiceInputs(self.cfg);self.runs=PSpiceRuns(self.cfg,self.inputs,PSpiceDat(self.cfg));self.main=self.src/'test.cir';self.lib=self.src/'dormant.lib';self.library='.SUBCKT UNUSED A B\nUROM A B ROM_MODEL FILE=|ROM_FILE|\n.ENDS UNUSED\n';self.circuit='* title\n.LIB "dormant.lib"\nV1 IN 0 DC 5\nR1 IN 0 1k\n.DC V1 5 5 1\n.END\n'
 def prepared(self,circuit=None,library=None):
  self.main.write_text(self.circuit if circuit is None else circuit,encoding='utf-8');self.lib.write_text(self.library if library is None else library,encoding='utf-8');sid=self.inputs.prepare(str(self.main))['simulationId'];return sid,self.inputs.inputs[sid]
 def test_literal_builtins_prove_dormant_file_template_and_keep_bytes(self):
  sid,row=self.prepared(library='--------------------\n'+self.library);p=self.runs.plan(sid,'dc');d,_,record=self.runs._load(p['planId']);proof=record['plan']['payload']['modelUseProof'];self.assertEqual(proof['modelRequests'],0);self.assertEqual(proof['subcircuitRequests'],0);self.assertEqual(proof['builtinDevices'],2);self.assertEqual(proof['inactiveDigitalFileTemplates'],1);result=self.runs.rebased_inputs(d,record['plan']['payload']);self.assertEqual(result['deps/file-001.lib'],('--------------------\n'+self.library).encode())
 def test_actual_model_requests_and_expressions_remain_refused(self):
  for line in ('D1 IN 0 D_FROM_LIB','X1 IN 0 UNUSED','U1 IN 0 ROM_MODEL','R1 IN 0 R_MODEL','R1 IN 0 {R_VALUE}'):
   sid,_=self.prepared(self.circuit.replace('R1 IN 0 1k',line))
   with self.subTest(line=line),self.assertRaises(CadenceError):self.runs.plan(sid,'dc')
  sid,_=self.prepared(self.circuit.replace('R1 IN 0 1k','.PARAM R_VALUE=1k\nR1 IN 0 1k'))
  with self.assertRaises(CadenceError):self.runs.plan(sid,'dc')
 def test_eager_library_and_global_control_or_unclosed_scope_refused(self):
  for circuit,lib in ((self.circuit.replace('.LIB','.INC'),self.library),(self.circuit,'.CONTROL\n.ENDC\n'+self.library),(self.circuit,self.library.replace('.ENDS UNUSED\n','')),(self.circuit,'.MODEL M D DLL=outside.dll\n'+self.library)):
   sid,_=self.prepared(circuit,lib)
   with self.assertRaises(CadenceError):self.runs.plan(sid,'dc')
 def test_reference_binding_and_proof_tampering_refused(self):
  sid,row=self.prepared();files={f['relativePath']:(row['directory']/f['relativePath']).read_bytes() for f in row['manifest']['files']};bad=json.loads(json.dumps(row['manifest']['files']));bad[0]['references'][0]['targetRelativePath']='input.cir'
  with self.assertRaises(CadenceError):execution_closure(row['directory'],files,bad)
  plan=self.runs.plan(sid,'dc');d,_,record=self.runs._load(plan['planId']);payload=record['plan']['payload'];payload['modelUseProof']['modelRequests']=1
  with self.assertRaises(CadenceError):self.runs.preflight(payload)
 def test_original_strict_inputs_without_embedded_forms_need_no_exemption(self):
  sid,row=self.prepared(library='.MODEL DTEST D\n');p=self.runs.plan(sid,'dc');d,_,record=self.runs._load(p['planId']);self.assertIsNone(record['plan']['payload']['modelUseProof'])
  with self.assertRaises(CadenceError):execution_preflight('+ FILE=|ROM_FILE|')
 def test_opaque_encrypted_library_scope_remains_refused(self):
  for marker in ('$CDNENCSTART', '$CDNENCSTART\nopaque_payload\n$CDNENCEND'):
   sid,_=self.prepared(library=self.library+marker+'\n')
   with self.subTest(marker=marker),self.assertRaises(CadenceError) as error:self.runs.plan(sid,'dc')
   self.assertEqual(error.exception.code,'unsupported_embedded_reference')
