import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_profile_circuits import PSpiceProfileCircuits

class ProfileCircuitTaskTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  install=self.root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  self.source=self.root/'source';self.source.mkdir();(self.source/'main.lib').write_text('.LIB "child.inc"\n.MODEL OWN D(IS=1e-14)\n');(self.source/'child.inc').write_text('.MODEL CHILD D(IS=2e-14)\n')
  self.cfg=Config(install,self.root/'work',(self.source,));self.net=self.cfg.workspace_root/'accepted-net';self.net.mkdir()
  desc={'projectTarget':'sample.opj','designTarget':'sample.dsn','profileTarget':'sim/ac.sim','netlistTarget':'sim/root.net','aliasesTarget':'sim/root.als','circuitTarget':'sim/ac/ac.cir','profileName':'ac','scope':'test_fixture'}
  files=[]
  for name in ('sample.opj','sample.dsn','sim/ac.sim','sim/root.net','sim/root.als'):
   target=self.net/'project'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('* own fixture\n');files.append({'relativePath':'project/'+name,'sha256':sha256(target)})
  write_json(self.net/'netlist-artifacts.json',{'files':files})
  self.service=PSpiceProfileCircuits(self.cfg,None,PSpiceInputs(self.cfg))
  self.row={'plan':{'payload':{'snapshot':{'description':desc}}}}
  self.result={'artifact':{'sha256':sha256(self.net/'netlist-artifacts.json')},'sourceDesignRevision':'a'*64}
  mock=patch.object(self.service,'_net',return_value=(self.net,self.row,self.result));mock.start();self.addCleanup(mock.stop)

 def plan(self,directives=None):
  return self.service.plan('a'*32,'b'*64,[str(self.source/'main.lib')],True,directives or ['.AC LIN 100 0.1 200'])

 def payload(self,plan):
  d,_,row=self.service._load(plan['planId']);return d,row['plan']['payload']

 def test_explicit_transitive_closure_stages_only_frozen_model_bytes_and_references(self):
  plan=self.plan();d,p=self.payload(plan);self.service._stage(d,p)
  _,manifest=self.service._models(p);self.assertEqual(len(manifest['files']),3)
  staged=json.loads((d/'staged-inputs.json').read_text());self.assertEqual(len(staged['files']),8)
  main=d/'project/models'/p['models']['libraries'][0]
  self.assertIn((d/'project/models'/manifest['files'][2]['relativePath']).as_posix(),main.read_text())
  self.assertEqual((self.source/'main.lib').read_text(),'.LIB "child.inc"\n.MODEL OWN D(IS=1e-14)\n')

 def test_changed_model_source_refuses_before_worker_or_stage(self):
  plan=self.plan();(self.source/'child.inc').write_text('changed')
  with self.assertRaises(CadenceError) as caught:self.service.apply(plan['planId'],plan['planDigest'],'never-start')
  self.assertEqual(caught.exception.code,'source_changed');d,_=self.payload(plan);self.assertEqual({x.name for x in d.iterdir()},{'plan.json'})

 def test_changed_frozen_model_is_not_recovered_from_live_source(self):
  plan=self.plan();_,p=self.payload(plan);root,manifest=self.service._models(p)
  (root/manifest['files'][1]['originalRelativePath']).write_text('changed')
  with self.assertRaises(CadenceError) as caught:self.service.preflight(p)
  self.assertEqual(caught.exception.code,'target_changed')

 def test_staging_detects_source_net_changed_after_artifact_check(self):
  plan=self.plan();d,p=self.payload(plan);(self.net/'project/sim/root.net').write_text('changed')
  with self.assertRaises(CadenceError) as caught:self.service._stage(d,p)
  self.assertEqual(caught.exception.code,'target_changed')

 def test_missing_analysis_or_unallowed_library_path_refuses(self):
  with self.assertRaises(CadenceError):self.plan(['.OPTIONS ADVCONV'])
  outside=self.root/'outside.lib';outside.write_text('.MODEL OUTSIDE D\n')
  with self.assertRaises(CadenceError) as caught:self.service.plan('a'*32,'b'*64,[str(outside)],True,['.OP'])
  self.assertEqual(caught.exception.code,'path_denied')

 def test_extended_budget_is_frozen_and_retained_when_preparing_verified_output(self):
  plan=self.service.plan('a'*32,'b'*64,[str(self.source/'main.lib')],True,['.OP'],'extended')
  d,p=self.payload(plan);self.assertEqual(p['inputBudget'],'extended');self.assertEqual(plan['preview']['inputBudget'],'extended')
  row=self.service._load(plan['planId'])[2];row['state']='verified'
  (d/'input.cir').write_text('* own circuit\n.OP\n.END\n')
  with patch.object(self.service,'_load',return_value=(d,d/'plan.json',row)),patch.object(self.service,'_verified_result',return_value={'circuitRelativePath':'input.cir','artifact':{'sha256':'a'*64},'sourceDesignRevision':'a'*64}):
   opened=self.service.open_input(plan['planId'],plan['planDigest'])
  self.assertEqual(opened['inputBudget'],'extended')

 def test_oversized_declared_directives_refuse_before_creating_unreadable_plan(self):
  with self.assertRaises(CadenceError) as caught:self.plan(['.AC '+'1'*4090]*16)
  self.assertEqual(caught.exception.code,'plan_limit');self.assertEqual(list(self.service.root.glob('plan-*')),[])

 def inherited_plan(self):
  ini=self.source/'global.ini';ini.write_text('[PSPICE NETLIST]\nLINE1=.lib "main.lib"\n')
  root=self.cfg.workspace_root/'query';root.mkdir();(root/'selected.ini').write_bytes(ini.read_bytes())
  (root/'native-result.json').write_text('{}');(root/'configuration-proof.json').write_text('{}')
  origin={'sourceIni':str(ini),'sourceIniSha256':sha256(ini),'snapshotDirectory':str(root),
          'selectedIniSha256':sha256(root/'selected.ini'),'nativeResultSha256':sha256(root/'native-result.json'),
          'proofSha256':sha256(root/'configuration-proof.json'),'selectedLibraries':[str(self.source/'main.lib')],'scope':'unit_fixture'}
  with patch('cadence_mcp.pspice_profile_circuits.inspect_global_selection',return_value=origin):
   plan=self.service.plan('a'*32,'b'*64,[],True,['.OP'],configuration_ini=str(ini))
  return plan,ini,root

 def test_inherited_ini_change_refuses_before_worker(self):
  plan,ini,_=self.inherited_plan();ini.write_text('changed')
  with self.assertRaises(CadenceError) as caught:self.service.apply(plan['planId'],plan['planDigest'],'no-worker')
  self.assertEqual(caught.exception.code,'source_changed');d,_=self.payload(plan);self.assertEqual({x.name for x in d.iterdir()},{'plan.json'})

 def test_native_configuration_proof_tamper_is_not_recomputed_from_live_ini(self):
  plan,_,root=self.inherited_plan();(root/'configuration-proof.json').write_text('changed')
  with self.assertRaises(CadenceError) as caught:self.service.preflight(self.payload(plan)[1])
  self.assertEqual(caught.exception.code,'source_changed')

 def test_configuration_provenance_is_copied_and_hashed_in_task(self):
  plan,_,root=self.inherited_plan();d,p=self.payload(plan);self.service._stage(d,p)
  self.assertEqual(p['configurationMode'],'inherited_global_library_selection')
  staged=json.loads((d/'staged-inputs.json').read_text())
  for name in ('selected.ini','native-result.json','configuration-proof.json'):
   self.assertEqual((d/'configuration-origin'/name).read_bytes(),(root/name).read_bytes())
   self.assertTrue(any(f['relativePath']=='configuration-origin/'+name and f['sha256']==sha256(root/name) for f in staged['files']))

 def test_wrong_directive_after_successful_native_receipt_is_rejected(self):
  plan=self.plan();d,p=self.payload(plan);circuit=self.service._stage(d,p);circuit.write_text('.AC LIN 99 0.1 200\n.END\n')
  (d/'generate.tcl').write_text('# fixture')
  write_json(d/'worker-process.json',{'pid':123,'state':'exited','returnCode':0,'remainingOwnedProcesses':0,'rootExitSignalConfirmed':True,'observedProcessExitSignalsConfirmed':True})
  write_json(d/'native-result.json',{'jobId':plan['planId'],'pid':123,'invocationReturned':True,'phase':'returned','loadResult':'0','libincResult':'0','updateResult':'0','error':'','cirPath':str(circuit)})
  with self.assertRaises(CadenceError) as caught:self.service.verify(d,p,True)
  self.assertEqual(caught.exception.code,'profile_directive_mismatch');self.assertFalse((d/'circuit-artifacts.json').exists())

if __name__=='__main__':unittest.main()
