import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_runs import PSpiceRuns,expectations_valid
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
