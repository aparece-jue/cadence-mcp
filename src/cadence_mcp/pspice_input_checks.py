"""Durable native parser/setup checks over a frozen prepared input closure."""
import json
from datetime import datetime,timezone
from pathlib import Path
from .core import CadenceError,checked_path,sha256,write_json
from .isolated_jobs import IsolatedJobs
from .environment import ADAPTERS
from .pspice_runs import PSpiceRuns,RELATIVE,execution_preflight
from .pspice_output import parse_out
from .pspice_diagnostics import failure_for_output

KEYS=('relativePath','preparedSha256','originalRelativePath','sourceSha256','references')

class PSpiceInputChecks(IsolatedJobs):
    kind='pspice_input_check'
    def __init__(self,config,inputs):
        super().__init__(config);self.inputs=inputs

    def plan(self,simulation_id,timeout_seconds=None):
        timeout=self.config.timeout_seconds if timeout_seconds is None else timeout_seconds
        if type(timeout) is not int or not 1<=timeout<=self.config.timeout_seconds:raise CadenceError('invalid_input_check','Timeout must be within the configured host bound.')
        with self.inputs.lock:
            self.inputs.get(simulation_id);entry=self.inputs.inputs[simulation_id];manifest=entry['manifest']
            payload={'simulationId':simulation_id,'preparedDirectory':str(entry['directory']),
                     'manifestHash':entry['manifestHash'],'sourceFingerprint':manifest['sourceFingerprint'],
                     'files':[{k:f[k] for k in KEYS} for f in manifest['files']],
                     'analysisTypes':manifest['analyses'],'timeoutSeconds':timeout}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Input-check plan exceeds durable bound.')
            self.preflight(payload);return self.create_plan(payload)

    def preflight(self,p):
        directory=checked_path(p['preparedDirectory'],(self.config.workspace_root,))
        manifestpath=checked_path(str(directory/'input-manifest.json'),(directory,))
        if sha256(manifestpath)!=p['manifestHash']:raise CadenceError('target_changed','Prepared input manifest changed.')
        manifest=json.loads(manifestpath.read_text(encoding='utf-8'))
        if (p['sourceFingerprint']!=manifest['sourceFingerprint'] or p['analysisTypes']!=manifest['analyses']
            or p['files']!=[{k:f[k] for k in KEYS} for f in manifest['files']]
            or type(p['timeoutSeconds']) is not int or not 1<=p['timeoutSeconds']<=self.config.timeout_seconds):raise CadenceError('invalid_plan','Input-check identity differs from the frozen prepared closure.')
        for f in p['files']:
            if not RELATIVE.fullmatch(f['relativePath']):raise CadenceError('invalid_plan','Unexpected prepared input path.')
            for relative,key in ((f['relativePath'],'preparedSha256'),(f['originalRelativePath'],'sourceSha256')):
                path=checked_path(str(directory/relative),(directory,))
                if sha256(path)!=f[key]:raise CadenceError('target_changed','Prepared or original input bytes changed.')
            execution_preflight((directory/f['relativePath']).read_text(encoding='utf-8'))

    def preview(self,p):
        return {'operation':'native_input_parser_setup','simulationId':p['simulationId'],
                'preparedManifestSha256':p['manifestHash'],
                'sourceFingerprint':p['sourceFingerprint'],'fileCount':len(p['files']),
                'analysisTypes':p['analysisTypes'],'timeoutSeconds':p['timeoutSeconds'],
                'analysisWillExecute':False,'implicitModelLookupClosureVerified':False}

    # Use exactly the established fixed rebasing/owned-process path; success verification is separate.
    rebased_inputs=PSpiceRuns.rebased_inputs
    execute=PSpiceRuns.execute
    worker_error=PSpiceRuns.worker_error

    def native_command(self,d,p):
        return [str(x) for x in (self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'check_pspice_input.tcl',self.config.install_root,d/'input.cir',d,ADAPTERS/'json.tcl')]

    def verify(self,d,p,native_completed):
        self.preflight(p);files=[]
        for relative,raw in self.rebased_inputs(d,p).items():
            path=checked_path(str(d/relative),(d,))
            if path.read_bytes()!=raw:raise CadenceError('simulation_input_changed','Checked job input differs from its frozen closure.')
            files.append({'relativePath':relative,'sha256':sha256(path),'size':path.stat().st_size})
        # Setup has no independent numerical oracle: missing native receipt cannot certify completion.
        if not (d/'receipt.json').exists():raise CadenceError('setup_completion_unverified','No native parser/setup receipt; retain artifacts without replay or successful validation.')
        receipt=checked_path(str(d/'receipt.json'),(d,))
        if receipt.stat().st_size>4096:raise CadenceError('invalid_worker_result','Input-check receipt exceeds bound.')
        native=json.loads(receipt.read_text(encoding='utf-8'))
        if (native.get('entryPoint')!='PSpiceSetupAnalysis' or type(native.get('caught')) is not int or native['caught']!=0
            or any(native.get(k)!='0' for k in ('setupReturn','finishReturn','cleanupReturn'))
            or native.get('analysisExecuted') is not False):raise CadenceError('pspice_input_invalid','Native setup did not confirm all fixed phases.')
        out=checked_path(str(d/'result.out'),(d,))
        if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Native setup OUT exceeds32MiB.')
        out_before=sha256(out);parsed=parse_out(out.read_text(encoding='cp1252'))
        if parsed['hasErrorDiagnostics']:raise failure_for_output(parsed)
        if 'CIRCUIT DESCRIPTION' not in out.read_text(encoding='cp1252'):raise CadenceError('incomplete_setup_output','No native circuit setup description was found.')
        for relative in ('result.out','receipt.json','setup.dat'):
            if relative=='setup.dat' and not (d/relative).exists():continue
            path=checked_path(str(d/relative),(d,))
            if path.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Input-check artifact exceeds32MiB.')
            files.append({'relativePath':relative,'sha256':sha256(path),'size':path.stat().st_size})
        if sha256(out)!=out_before:raise CadenceError('target_changed','Native setup OUT changed during verification.')
        self.preflight(p);ident=d.name.removeprefix('plan-')
        manifest={'planId':ident,'sourceFingerprint':p['sourceFingerprint'],'analysisTypes':p['analysisTypes'],
                  'simulationId':p['simulationId'],'preparedManifestSha256':p['manifestHash'],
                  'entryPoint':'PSpiceSetupAnalysis','files':files,'nativeParserSetupVerified':True,
                  'analysisExecuted':False,'solverSuccessVerified':False,'numericalAcceptanceVerified':False,
                  'diagnostics':parsed['diagnostics'],'diagnosticSummary':parsed['diagnosticSummary'],
                  'reportedVersions':parsed['reportedVersions'],'scope':'native_parse_setup_only'}
        target=d/'input-check-manifest.json'
        if target.exists():
            if json.loads(target.read_text(encoding='utf-8'))!=manifest:raise CadenceError('target_changed','Existing input-check manifest differs.')
        else:write_json(target,manifest)
        artifact={'artifactId':'input-check-'+ident,'kind':'pspice_input_validation_manifest','workspaceRelativePath':target.name,
                  'sha256':sha256(target),'size':target.stat().st_size,'producedByJob':ident,
                  'sourceFingerprint':p['sourceFingerprint'],'sourceKind':'file_fingerprint',
                  'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered',
                'artifact':artifact,'nativeCompletionVerified':native_completed,'nativeReceiptVerified':True,
                'simulationId':p['simulationId'],'preparedManifestSha256':p['manifestHash'],
                'nativeParserSetupVerified':True,'analysisExecuted':False,'solverSuccessVerified':False,
                'numericalAcceptanceVerified':False,'sourceModified':False,'designPassed':None,
                'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['numerical_results','convergence','implicit_model_lookup_closure','all_spice_dialects','electrical_design_safety']}

    def _verified_result(self,d,row):
        result=super()._verified_result(d,row);manifest=json.loads((d/'input-check-manifest.json').read_text(encoding='utf-8'))
        for f in manifest['files']:
            if f['relativePath'] not in ('result.out','receipt.json','setup.dat') and not RELATIVE.fullmatch(f['relativePath']):raise CadenceError('invalid_worker_result','Unexpected input-check artifact path.')
            path=checked_path(str(d/f['relativePath']),(d,))
            if path.stat().st_size!=f['size'] or sha256(path)!=f['sha256']:raise CadenceError('target_changed','A previously checked input/output changed.')
        return result

    def inspect(self,plan_id,plan_digest):
        guard=self._guard()
        try:
            d,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified input checks can be inspected as successful.')
            result=self._verified_result(d,row)
            return {**json.loads((d/'input-check-manifest.json').read_text(encoding='utf-8')),
                    'nativeCompletionVerified':result['nativeCompletionVerified'],'manifestSha256':result['artifact']['sha256']}
        finally:guard.close()
