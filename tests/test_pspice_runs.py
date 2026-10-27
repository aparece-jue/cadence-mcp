import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_runs import PSpiceRuns,expectations_valid,execution_preflight,decode_run_output
class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=root/'sources';source.mkdir();self.source=source/'test.cir'
        (source/'one.inc').write_text('.PARAM R=1000\n')
        self.source.write_text('* fixture\n.INC one.inc\nV1 1 0 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE\n.END\n')
        self.config=Config(install,root/'work',(source,),30);self.inputs=PSpiceInputs(self.config);self.data=PSpiceDat(self.config);self.runs=PSpiceRuns(self.config,self.inputs,self.data)
        self.sid=self.inputs.prepare(str(self.source))['simulationId']
    def point(self):return {'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}
    def test_rebases_nested_closure_into_new_job_without_source_mutation(self):
        before=sha256(self.source);p=self.runs.plan(self.sid,'dc',[self.point()]);directory,_,row=self.runs._load(p['planId'])
        files=self.runs.rebased_inputs(directory,row['plan']['payload']);self.assertIn(str((directory/'deps/file-001.inc').as_posix()).encode(),files['input.cir'])
        self.assertNotIn(str(self.inputs.inputs[self.sid]['directory'].as_posix()).encode(),files['input.cir']);self.assertEqual(before,sha256(self.source))
    def test_parameter_step_refuses_single_analysis_engine_but_cli_can_plan(self):
        from cadence_mcp.pspice_cli_runs import PSpiceCliRuns
        self.source.write_text('* step fixture\n.PARAM RV=500\nV1 IN 0 DC 0 AC 1\nR1 IN 0 {RV}\n.STEP PARAM RV LIST 500 1k\n.AC LIN 3 10 30\n.PROBE64 V([IN])\n.END\n')
        sid=self.inputs.prepare(str(self.source))['simulationId']
        with self.assertRaises(CadenceError) as caught:self.runs.plan(sid,'ac')
        self.assertEqual(caught.exception.code,'parameter_step_requires_cli')
        self.assertEqual(list(self.runs.root.glob('plan-*')),[])
        cli=PSpiceCliRuns(self.config,self.inputs,PSpiceDat(self.config))
        self.assertEqual(cli.plan(sid,'ac')['preview']['analysis'],'ac')

    def test_preserved_model_bytes_survive_job_rebase_and_policy_checks(self):
        model=self.source.parent/'legacy.lib';raw=b'* legacy\x81E\r\n.MODEL DTEST D\x81E\r\n';model.write_bytes(raw)
        self.source.write_bytes(b'* input\r\n.LIB "legacy.lib"\r\n.DC V1 5 5 1\r\n.PROBE64 V(*)\r\n.END\r\n')
        sid=self.inputs.prepare(str(self.source),'preserve-bytes')['simulationId'];plan=self.runs.plan(sid,'dc');directory,_,row=self.runs._load(plan['planId']);payload=row['plan']['payload'];rebased=self.runs.rebased_inputs(directory,payload)
        self.assertEqual(rebased['deps/file-001.lib'],raw)
        self.assertTrue(rebased['input.cir'].endswith(b'.END\r\n'))
        self.assertEqual(payload['inputEncoding'],'preserve-bytes')
        payload['inputEncoding']='utf-8'
        with self.assertRaises(CadenceError):self.runs.preflight(payload)

    def test_numeric_core_path_is_not_a_file_but_actual_file_forms_still_refuse(self):
        execution_preflight('.MODEL Ktest CORE AREA=.65 PATH=8.0 MS=1.2E6')
        for text in ('.MODEL Ktest CORE PATH=other.dat', '.MODEL Ktest CORE PATH=8 FILE=other.dat',
                     '.OPTIONS PATH=8', '.MODEL Ktest CORE PATH=8evil', '+ FILE=|JEDEC_FILE|'):
            with self.subTest(text=text),self.assertRaises(CadenceError):execution_preflight(text)

    def test_extended_plan_record_remains_bounded_and_reloadable(self):
        lines=['* extended fixture']
        for i in range(200):
            (self.source.parent/f'm{i}.lib').write_text('* empty model\n')
            lines.append(f'.LIB "m{i}.lib"')
        self.source.write_text('\n'.join(lines)+'\n.DC V1 5 5 1\n.END\n')
        sid=self.inputs.prepare(str(self.source),'utf-8','extended')['simulationId']
        plan=self.runs.plan(sid,'dc');directory,_,row=self.runs._load(plan['planId'])
        self.assertEqual(len(row['plan']['payload']['files']),201)
        self.assertGreater((directory/'plan.json').stat().st_size,65536)
        self.assertLess((directory/'plan.json').stat().st_size,self.runs.max_record_bytes)
        self.assertEqual(len(self.runs.rebased_inputs(directory,row['plan']['payload'])),201)

    def test_undefined_out_bytes_only_allowed_in_explicit_full_comments(self):
        raw=b"* legacy comment \x81E\r\nERROR(ORPSIM-12345): failed\r\n"
        with self.assertRaises(UnicodeDecodeError):decode_run_output(raw,{})
        text=decode_run_output(raw,{'inputEncoding':'preserve-bytes'})
        self.assertIn(r'\x81E',text)
        self.assertIn('ERROR(ORPSIM-12345)',text)
        with self.assertRaises(CadenceError):decode_run_output(b'ERROR(ORPSIM-12345): \x81E',{'inputEncoding':'preserve-bytes'})

    def test_invalid_sample_numbers_analysis_and_timeout_refused(self):
        for field,value in [('row',True),('real',float('nan')),('absoluteTolerance',0),('traceName','bad\nname')]:
            p=self.point();p[field]=value;self.assertFalse(expectations_valid([p]))
        for analysis,timeout in [('op',1),('dc',31),('dc',True)]:
            with self.assertRaises(CadenceError):self.runs.plan(self.sid,analysis,timeout_seconds=timeout)
        with self.assertRaises(CadenceError):self.runs.plan(self.sid,'ac')
    def test_unsupported_execution_file_forms_refused(self):
        for addition in ['.CONTROL\n.ENDC','B1 1 0 V=FILE=other.dat','.OPTIONS LIBPATH=other']:
            self.source.write_text('* fixture\n'+addition+'\n.DC V1 5 5 1\n.END\n');sid=self.inputs.prepare(str(self.source))['simulationId']
            with self.assertRaises(CadenceError):self.runs.plan(sid,'dc')
    def test_pending_cancel_and_changed_prepared_closure_never_execute(self):
        p=self.runs.plan(self.sid,'dc');self.runs.cancel(p['planId'],p['planDigest'])
        with patch.object(self.runs,'execute') as execute:
            with self.assertRaises(CadenceError):self.runs.apply(p['planId'],p['planDigest'],'cancel')
            execute.assert_not_called()
        p=self.runs.plan(self.sid,'dc');(self.inputs.inputs[self.sid]['directory']/'deps/file-001.inc').write_bytes(b'changed')
        with patch.object(self.runs,'execute') as execute:
            with self.assertRaises(CadenceError):self.runs.apply(p['planId'],p['planDigest'],'stale')
            execute.assert_not_called()
    def test_cached_result_checks_every_output_not_just_manifest(self):
        p=self.runs.plan(self.sid,'dc');directory,_,_=self.runs._load(p['planId']);out=directory/'result.dat';out.write_bytes(b'original')
        manifest=directory/'run-artifacts.json';write_json(manifest,{'files':[{'relativePath':'result.dat','sha256':sha256(out)}]})
        row={'result':{'artifact':{'workspaceRelativePath':'run-artifacts.json','sha256':sha256(manifest)}}}
        self.runs._verified_result(directory,row);out.write_bytes(b'tampered')
        with self.assertRaises(CadenceError):self.runs._verified_result(directory,row)
