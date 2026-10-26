"""Persistent fixed engine jobs over immutable prepared input closures."""
from datetime import datetime,timezone
from pathlib import Path
import json,math,re
from .core import CadenceError,Config,checked_path,sha256,write_json
from .environment import ADAPTERS,process_env
from .isolated_jobs import IsolatedJobs
from .process_tree import run_owned_process
from .pspice_dat import PSpiceDat
from .pspice_output import parse_out
from .pspice_diagnostics import failure_for_output
from .gui_jobs import durable_json
from .pspice_model_use import prove_unused_libraries

ANALYSES={'dc':('DC','DC Sweep'),'ac':('AC','AC Sweep'),'transient':('TRAN','Transient Analysis')}
RELATIVE=re.compile(r'(?:input\.cir|deps/file-\d{3}\.[a-z0-9]{1,8})')
DIRECTIVES={'.INC','.INCLUDE','.LIB','.DC','.AC','.TRAN','.OP','.END','.MODEL','.SUBCKT','.ENDS','.PARAM','.FUNC','.GLOBAL','.OPTIONS','.TEMP','.IC','.NODESET','.PROBE','.PROBE64','.PRINT','.MEAS','.MEASURE','.FOUR','.TF','.NOISE','.ALIASES','.ENDALIASES'}

def execution_preflight(text):
    """Reject unsupported file/control forms; this does not certify all SPICE syntax."""
    for line in text.splitlines():
        value=line.strip()
        if not value or value.startswith('*'):continue
        first=value.split()[0].upper()
        if first.startswith('.') and first not in DIRECTIVES:raise CadenceError('unsupported_execution_directive','This directive requires a dedicated execution contract.')
        checked=value
        if re.match(r'^\.MODEL\s+\S+\s+CORE\b',value,re.I):
            checked=re.sub(r'\bPATH\s*=\s*\+?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?=\s|\)|$)','',value,flags=re.I)
        if re.search(r'\b(?:FILE|PATH|LIBPATH|DLL|STMLIB|STIMULUS|TABLEFILE)\s*=',checked,re.I):raise CadenceError('unsupported_embedded_reference','Embedded file/path sources require a dedicated resolver.')

def execution_closure(root,files,rows):
    try:
        for raw in files.values():execution_preflight(raw.decode('utf-8-sig',errors='surrogateescape'))
        return None
    except CadenceError as original:
        if original.code!='unsupported_embedded_reference':raise
        try:return prove_unused_libraries(root,files,rows,execution_preflight)
        except CadenceError:raise original

def decode_run_output(raw,payload):
    """Preserve raw artifacts; only escape undefined CP1252 bytes on full comment lines."""
    if payload.get('inputEncoding')!='preserve-bytes':return raw.decode('cp1252')
    lines=[]
    for line in raw.splitlines(keepends=True):
        try:lines.append(line.decode('cp1252'))
        except UnicodeDecodeError as error:
            if not line.lstrip().startswith(b'*'):
                raise CadenceError('unsupported_output_encoding','Undefined OUT bytes outside full comments require explicit handling.','verify') from error
            lines.append(line.decode('cp1252',errors='backslashreplace'))
    return ''.join(lines)

def expectations_valid(rows):
    if not isinstance(rows,list) or len(rows)>32:return False
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'block','row','traceName','real','imaginary','absoluteTolerance','relativeTolerance'}:return False
        if any(type(row[k]) is not int or not 0<=row[k]<=bound for k,bound in [('block',127),('row',99999)]):return False
        if not isinstance(row['traceName'],str) or not 1<=len(row['traceName'])<=512 or any(c in row['traceName'] for c in '\x00\r\n'):return False
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ('real','absoluteTolerance','relativeTolerance')):return False
        if row['imaginary'] is not None and (type(row['imaginary']) not in (int,float) or not math.isfinite(row['imaginary'])):return False
        if not 0<row['absoluteTolerance']<=1000000 or not 0<=row['relativeTolerance']<=1:return False
    return True

class PSpiceRuns(IsolatedJobs):
    kind='pspice_engine_run'
    max_record_bytes=262144
    def __init__(self,config,inputs,data):
        super().__init__(config);self.inputs=inputs;self.data=data
    def plan(self,simulation_id,analysis,expected_samples=None,timeout_seconds=None):
        expected=[] if expected_samples is None else expected_samples
        timeout=self.config.timeout_seconds if timeout_seconds is None else timeout_seconds
        if analysis not in ANALYSES or not expectations_valid(expected) or type(timeout) is not int or not 1<=timeout<=self.config.timeout_seconds:raise CadenceError('invalid_simulation_plan','Use a supported analysis, bounded trace-row expectations and timeout within the host limit.')
        with self.inputs.lock:
            self.inputs.get(simulation_id);row=self.inputs.inputs[simulation_id];manifest=row['manifest']
            if ANALYSES[analysis][0] not in manifest['analyses']:raise CadenceError('analysis_not_found','The selected analysis is absent from the prepared closure.')
            files=[]
            for f in manifest['files']:
                relative=f['relativePath']
                if not RELATIVE.fullmatch(relative):raise CadenceError('invalid_input_manifest','Input file identity is not a generated path.')
                files.append({k:f[k] for k in ('relativePath','preparedSha256','originalRelativePath','sourceSha256','references')})
            proof=execution_closure(row['directory'],{f['relativePath']:(row['directory']/f['relativePath']).read_bytes() for f in files},files)
            payload={'modelUseProof':proof,'inputEncoding':manifest.get('inputEncoding','utf-8'),'inputBudget':manifest.get('inputBudget','standard'),'simulationId':simulation_id,'preparedDirectory':str(row['directory']),'manifestHash':row['manifestHash'],'sourceFingerprint':manifest['sourceFingerprint'],'files':files,'analysis':analysis,'expectedSamples':expected,'timeoutSeconds':timeout}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>196608:raise CadenceError('plan_limit','Simulation plan exceeds durable record bound.')
            self.preflight(payload);return self.create_plan(payload)
    def backend_name(self):return 'independent_pspice_engine_tcl'
    def extra_scope(self):return 'declared_native_measurement_fields_only'
    def backend_not_checked(self):return ['cli_backend']
    def preview(self,p):
        return {k:p[k] for k in ('simulationId','sourceFingerprint','analysis','timeoutSeconds','expectedSamples')}|{'fileCount':len(p['files']),'backend':self.backend_name(),'implicitModelLookupVerified':False,'modelUseProof':p.get('modelUseProof')}
    def preflight(self,p):
        directory=checked_path(p['preparedDirectory'],(self.config.workspace_root,))
        if sha256(checked_path(str(directory/'input-manifest.json'),(directory,)))!=p['manifestHash']:raise CadenceError('target_changed','Prepared input manifest changed after planning.')
        if p.get('inputEncoding','utf-8') not in ('utf-8','preserve-bytes') or p.get('inputBudget','standard') not in ('standard','extended'):raise CadenceError('invalid_plan','Unsupported input encoding/budget policy.')
        manifest=json.loads((directory/'input-manifest.json').read_text(encoding='utf-8'))
        if p.get('inputEncoding','utf-8')!=manifest.get('inputEncoding','utf-8') or p.get('inputBudget','standard')!=manifest.get('inputBudget','standard'):raise CadenceError('invalid_plan','Input policies differ from immutable manifest.')
        if p['analysis'] not in ANALYSES or not expectations_valid(p['expectedSamples']) or type(p['timeoutSeconds']) is not int or not 1<=p['timeoutSeconds']<=self.config.timeout_seconds:raise CadenceError('invalid_plan','Invalid fixed simulation payload.')
        for f in p['files']:
            if not RELATIVE.fullmatch(f['relativePath']):raise CadenceError('invalid_plan','Input path is not a generated relative name.')
            for relative,key in [(f['relativePath'],'preparedSha256'),(f['originalRelativePath'],'sourceSha256')]:
                if sha256(checked_path(str(directory/relative),(directory,)))!=f[key]:raise CadenceError('target_changed','Prepared input bytes changed after planning.')
        if execution_closure(directory,{f['relativePath']:(directory/f['relativePath']).read_bytes() for f in p['files']},p['files'])!=p.get('modelUseProof'):raise CadenceError('model_use_changed','Execution-scope proof differs from the immutable plan.')
    def rebased_inputs(self,directory,p):
        preserve=p.get('inputEncoding')=='preserve-bytes'
        source=Path(p['preparedDirectory']);names={f['relativePath'] for f in p['files']};result={}
        for f in p['files']:
            raw=(source/f['relativePath']).read_bytes();lines=raw.decode('utf-8-sig',errors='surrogateescape' if preserve else 'strict').splitlines(keepends=preserve)
            for ref in f['references']:
                if ref['targetRelativePath'] not in names or ref['directive'] not in ('INC','INCLUDE','LIB') or type(ref['line']) is not int or not 1<=ref['line']<=len(lines):raise CadenceError('invalid_input_manifest','Invalid closure reference.')
                old=lines[ref['line']-1];ending='\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else '\r' if old.endswith('\r') else ''
                lines[ref['line']-1]='.'+ref['directive']+' "'+(directory/ref['targetRelativePath']).as_posix()+'"'+(ending if preserve else '')
            text=''.join(lines) if preserve else '\n'.join(lines)+'\n';result[f['relativePath']]=text.encode('utf-8',errors='surrogateescape' if preserve else 'strict')
            if preserve and raw.startswith(b'\xef\xbb\xbf'):result[f['relativePath']]=b'\xef\xbb\xbf'+result[f['relativePath']]
        if execution_closure(directory,result,p['files'])!=p.get('modelUseProof'):raise CadenceError('model_use_changed','Rebased execution scope differs from its plan.')
        return result
    def execute(self,directory,p,cancel,on_started):
        self.preflight(p)
        for relative,raw in self.rebased_inputs(directory,p).items():
            target=directory/relative;target.parent.mkdir(exist_ok=True)
            with target.open('xb') as stream:stream.write(raw)
        self.preflight(p)
        return run_owned_process(self.native_command(directory,p),directory,process_env(self.config),p['timeoutSeconds'],cancel=cancel,on_started=on_started)
    def native_command(self,directory,p):
        return [str(x) for x in [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_analysis.tcl',self.config.install_root,directory/'input.cir',directory,p['analysis']]]
    def worker_error(self,directory,p,process):
        # Native status/OUT classification is evidence-based; timeout alone is never a license diagnosis.
        path=directory/'result.out'
        if path.is_file() and path.stat().st_size<=32*1024*1024:
            try:
                data=parse_out(decode_run_output(path.read_bytes(),p))
                if data['hasErrorDiagnostics']:return failure_for_output(data,'solver')
            except (CadenceError,UnicodeError):pass
        return CadenceError('pspice_engine_failed','The owned PSpice engine failed; inspect the retained task receipt.','solver')
    def confirm_receipt(self,directory,p):
        receipt=checked_path(str(directory/'receipt.json'),(directory,))
        if receipt.stat().st_size>4096:raise CadenceError('invalid_worker_result','Simulation receipt exceeds bound.')
        r=json.loads(receipt.read_text(encoding='utf-8'))
        if type(r.get('caught')) is not int or r['caught']!=0 or set(r.get('returns',{}))!={'batchModeReturn','setupReturn','analysisReturn','finishReturn','cleanupReturn'} or any(r['returns'][k]!='0' for k in ('setupReturn','analysisReturn','finishReturn','cleanupReturn')):raise CadenceError('pspice_engine_failed','Engine did not confirm every planned phase.','verify')
    def confirm_output(self,text,p):
        if '**** Command: FINISH' not in text or 'JOB STATISTICS SUMMARY' not in text:raise CadenceError('incomplete_simulation_output','No completed/finished task output was found.','verify')
    def extra_artifacts(self,directory,p):return [],{}
    def output_names(self):return ('result.out','result.dat')
    def verify(self,directory,p,native_completed):
        self.preflight(p);expected=self.rebased_inputs(directory,p);files=[]
        for relative,raw in expected.items():
            target=checked_path(str(directory/relative),(directory,))
            if target.read_bytes()!=raw:raise CadenceError('simulation_input_changed','Job input closure differs from its immutable plan.','verify')
            files.append({'relativePath':relative,'sha256':sha256(target),'size':target.stat().st_size})
        if native_completed:self.confirm_receipt(directory,p)
        out=checked_path(str(directory/'result.out'),(directory,));dat=checked_path(str(directory/'result.dat'),(directory,))
        if max(out.stat().st_size,dat.stat().st_size)>32*1024*1024:raise CadenceError('output_limit','Simulation output exceeds bound.')
        before={name:sha256(path) for name,path in [('out',out),('dat',dat)]};text=decode_run_output(out.read_bytes(),p);parsed=parse_out(text)
        if parsed['hasErrorDiagnostics']:raise failure_for_output(parsed,'verify')
        self.confirm_output(text,p)
        internal=PSpiceDat(Config(self.config.install_root,self.config.workspace_root,(directory,),self.config.timeout_seconds))
        ident=internal.open(str(dat))['datId'];checked=[]
        try:
            blocks=internal.query(ident,'block',limit=1000)['items']
            if not blocks or any(b['analysisName']!=ANALYSES[p['analysis']][1] or not b['analogReadSupported'] or b['rowCount']==0 for b in blocks):raise CadenceError('unexpected_simulation_data','DAT analyses/rows do not match the planned analog run.','verify')
            for b in blocks:internal.samples(ident,b['index'],b['axis'],0,1) # Decoder checks every finite token before paging.
            for sample in p['expectedSamples']:
                value=internal.samples(ident,sample['block'],sample['traceName'],sample['row'],1)['items']
                if not value:raise CadenceError('simulation_expectation_mismatch','Expected sample row is absent.','verify')
                value=value[0];components=['real']+(['imaginary'] if sample['imaginary'] is not None else [])
                for component in components:
                    wanted=sample[component];actual=value[component]
                    if actual is None or abs(actual-wanted)>sample['absoluteTolerance']+sample['relativeTolerance']*abs(wanted):raise CadenceError('simulation_expectation_mismatch','A declared numerical sample differs from its independent expectation.','verify')
                checked.append({'block':sample['block'],'row':sample['row'],'traceName':sample['traceName'],'components':components,'observed':value})
        finally:internal.close(ident)
        if before!={'out':sha256(out),'dat':sha256(dat)}:raise CadenceError('target_changed','Simulation output changed while independently verifying.')
        extra_files,extra=self.extra_artifacts(directory,p);files.extend(extra_files)
        for relative in ('result.out','result.dat'):
            target=directory/relative;files.append({'relativePath':relative,'sha256':sha256(target),'size':target.stat().st_size})
        self.preflight(p);ident=directory.name.removeprefix('plan-')
        manifest={'planId':ident,'backend':self.backend_name(),'sourceFingerprint':p['sourceFingerprint'],'analysis':p['analysis'],'files':files,'reportedVersions':parsed['reportedVersions'],'numericalChecks':checked,'scope':'declared_trace_rows_only'}
        if extra:manifest.update(extra,scope=self.extra_scope())
        target=directory/'run-artifacts.json'
        if target.exists():
            if json.loads(target.read_text(encoding='utf-8'))!=manifest:raise CadenceError('target_changed','Existing run manifest differs from current verified artifacts.')
        else:write_json(target,manifest)
        artifact={'artifactId':'pspice-run-'+ident,'kind':'pspice_run_manifest','workspaceRelativePath':'run-artifacts.json','sha256':sha256(target),'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'backend':self.backend_name(),'nativeCompletionVerified':native_completed,'independentDatReadVerified':True,'jobAssociationVerified':True,'numericalAcceptanceVerified':bool(checked or extra.get('nativeMeasurementChecks')),'numericalAcceptanceScope':manifest['scope'],'declaredChecks':checked,'designPassed':None,'sourceModified':False,'notChecked':self.backend_not_checked()+['implicit_model_lookup_closure','full_spice_syntax','unrequested_waveform_values','occurrence_mapping','electrical_design_safety']+(['digital_logic_samples'] if any(b['dataTypeCode']!=0 for b in blocks) else [])}
    def _verified_result(self,directory,row):
        result=super()._verified_result(directory,row);manifest=json.loads((directory/'run-artifacts.json').read_text(encoding='utf-8'))
        for f in manifest['files']:
            if f['relativePath'] not in self.output_names() and not RELATIVE.fullmatch(f['relativePath']):raise CadenceError('invalid_worker_result','Unexpected artifact path in run manifest.')
            if sha256(checked_path(str(directory/f['relativePath']),(directory,)))!=f['sha256']:raise CadenceError('target_changed','A previously verified job input/output changed.')
        return result
    def open_dat(self,plan_id,plan_digest):
        guard=self._guard()
        try:
            directory,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified run data can be opened.')
            result=self._verified_result(directory,row)
            with self.data.lock:
                if len(self.data.sessions)>=32:raise CadenceError('session_limit','Too many imported DAT sessions.')
                internal=PSpiceDat(Config(self.config.install_root,self.config.workspace_root,(directory,),self.config.timeout_seconds))
                manifest=internal.open(str(directory/'result.dat'));ident=manifest['datId']
                manifest.update(provenance='verified_job_snapshot',jobAssociationVerified=True,solverSuccessVerified=True,producedByPlan=plan_id,runManifestSha256=result['artifact']['sha256'],numericalAcceptanceVerified=result['numericalAcceptanceVerified'])
                internal.sessions[ident]['manifest']=manifest;durable_json(internal.sessions[ident]['directory']/'manifest.json',manifest)
                self.data.sessions[ident]=internal.sessions.pop(ident);return manifest
        finally:guard.close()

    def inspect_output(self,plan_id,plan_digest):
        """Read OUT from a verified durable run, with no execution or root widening."""
        guard=self._guard()
        try:
            directory,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified run output can be inspected.')
            result=self._verified_result(directory,row)
            out=checked_path(str(directory/'result.out'),(directory,))
            if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','OUT exceeds 32 MiB.')
            raw=out.read_bytes()
            if len(raw)>32*1024*1024:raise CadenceError('output_limit','OUT exceeds 32 MiB.')
            report=parse_out(decode_run_output(raw,row['plan']['payload']))
            import hashlib
            fingerprint=hashlib.sha256(raw).hexdigest()
            manifest=json.loads((directory/'run-artifacts.json').read_text(encoding='utf-8'))
            expected=[f for f in manifest['files'] if f['relativePath']=='result.out']
            if len(expected)!=1 or expected[0]['sha256']!=fingerprint:raise CadenceError('target_changed','OUT bytes differ from the verified manifest.')
            self._verified_result(directory,row)
            native=bool(result['nativeCompletionVerified'])
            report.update(provenance='verified_job_snapshot',jobAssociationVerified=True,
                solverSuccessVerified=native,nativeCompletionVerified=native,
                producedByPlan=plan_id,sourceFingerprint=fingerprint,
                circuitSourceFingerprint=row['plan']['payload']['sourceFingerprint'],
                runManifestSha256=result['artifact']['sha256'],
                numericalAcceptanceVerified=result['numericalAcceptanceVerified'],
                numericalAcceptanceScope=result['numericalAcceptanceScope'],
                designPassed=None,encoding='cp1252')
            if native:report['notChecked'].remove('fresh_solver_run')
            return report
        finally:guard.close()
