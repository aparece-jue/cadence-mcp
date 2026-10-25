"""Native .MEASURE output from fixed complete-analysis jobs, separately from DAT statistics."""
import json, math, re, hashlib
from .pspice_measurement_units import annotate_measurements
from pathlib import Path
from .core import CadenceError, checked_path, sha256
from .environment import ADAPTERS
from .pspice_runs import PSpiceRuns, ANALYSES, execution_preflight

NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?'
NAME=r'[A-Za-z_][A-Za-z0-9_]{0,63}'
FIELDS=('value','at','from','to')

def declarations(texts,analysis):
    rows=[];names=set()
    for relative,text in texts.items():
        logical=[]
        for line in text.splitlines():
            stripped=line.strip()
            if not stripped or stripped.startswith('*'):continue
            if stripped.startswith('+') and logical:logical[-1]+=' '+stripped[1:].strip()
            else:logical.append(stripped)
        for line in logical:
            if not re.match(r'^\.MEAS(?:URE)?(?:\s|$)',line,re.I):continue
            m=re.fullmatch(r'\.MEAS(?:URE)?\s+(DC|AC|TRAN)\s+('+NAME+r')\s+(.{1,4096})',line,re.I)
            if not m or m[1].upper()!=ANALYSES[analysis][0] or m[2].casefold() in names:
                raise CadenceError('invalid_measurement_declaration','Use unique bounded native measurements matching the single selected analysis.')
            names.add(m[2].casefold());rows.append({'name':m[2],'analysis':m[1].upper(),'expression':m[3],'inputFile':relative})
            if len(rows)>64:raise CadenceError('measurement_limit','At most64 native measurement declarations per run.')
    if not rows:raise CadenceError('measurement_not_found','The prepared closure has no native .MEASURE declarations.')
    return rows

def parse_measurements(text):
    if '\x00' in text or len(text)>1024*1024:raise CadenceError('measurement_output_invalid','Native measurement text exceeds its format or size bound.')
    rows=[];names=set()
    for line_number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        m=re.fullmatch(r'\s*('+NAME+r'):\s*(.{1,8192}?)\s*',line)
        if not m or m[1].casefold() in names:raise CadenceError('measurement_output_invalid','Unknown or duplicate native measurement row.')
        names.add(m[1].casefold());body=m[2]
        row={'name':m[1],'line':line_number,'raw':line,'state':'evaluated','fields':{}}
        if body=='Evaluation Failed.':row.update(state='evaluation_failed',expression=None)
        else:
            n=re.fullmatch(r'(?:(?P<expression>.+?)=\s*)?(?P<value>'+NUMBER+r')(?P<suffix>(?:\s+(?:AT|FROM|TO)\s+'+NUMBER+r')*)',body,re.I)
            if not n:raise CadenceError('measurement_output_invalid','Unrecognized native numeric measurement syntax.')
            row['expression']=n['expression'];row['fields']['value']=float(n['value'].replace('D','E').replace('d','e'))
            for key,value in re.findall(r'\s+(AT|FROM|TO)\s+('+NUMBER+r')',n['suffix'],re.I):
                key=key.lower()
                if key in row['fields']:raise CadenceError('measurement_output_invalid','Repeated measurement result field.')
                row['fields'][key]=float(value.replace('D','E').replace('d','e'))
            if any(not math.isfinite(v) for v in row['fields'].values()):raise CadenceError('measurement_output_invalid','Nonfinite native measurement result.')
        rows.append(row)
        if len(rows)>64:raise CadenceError('measurement_limit','Too many native measurement results.')
    if not rows:raise CadenceError('measurement_output_invalid','No native measurement results.')
    return rows

def valid_expectations(rows,declared):
    if not isinstance(rows,list) or not 1<=len(rows)<=128:return False
    seen=set()
    for r in rows:
        if not isinstance(r,dict) or set(r)!={'name','field','expected','absoluteTolerance','relativeTolerance'}:return False
        if not isinstance(r['name'],str) or r['name'].casefold() not in declared or r['field'] not in FIELDS:return False
        key=(r['name'].casefold(),r['field'])
        if key in seen:return False
        seen.add(key)
        if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) for k in ('expected','absoluteTolerance','relativeTolerance')):return False
        if not 0<r['absoluteTolerance']<=1000000 or not 0<=r['relativeTolerance']<=1:return False
    return True

class PSpiceMeasurementRuns(PSpiceRuns):
    kind='pspice_measure_run'

    def plan(self,simulation_id,analysis,expected_measurements,timeout_seconds=None):
        timeout=self.config.timeout_seconds if timeout_seconds is None else timeout_seconds
        if analysis not in ANALYSES or type(timeout) is not int or not 1<=timeout<=self.config.timeout_seconds:
            raise CadenceError('invalid_simulation_plan','Choose one bounded supported analysis and timeout.')
        with self.inputs.lock:
            self.inputs.get(simulation_id);entry=self.inputs.inputs[simulation_id];manifest=entry['manifest']
            if manifest['analyses']!=[ANALYSES[analysis][0]]:raise CadenceError('unsupported_measurement_analyses','Complete-analysis measurements currently require exactly one selected analysis in the closure.')
            files=[{k:f[k] for k in ('relativePath','preparedSha256','originalRelativePath','sourceSha256','references')} for f in manifest['files']]
            texts={f['relativePath']:(entry['directory']/f['relativePath']).read_text(encoding='utf-8') for f in files}
            declared=declarations(texts,analysis)
            if not valid_expectations(expected_measurements,{r['name'].casefold() for r in declared}):raise CadenceError('invalid_measurement_expectations','Declare finite numeric expectations for named value/at/from/to fields.')
            payload={'simulationId':simulation_id,'preparedDirectory':str(entry['directory']),'manifestHash':entry['manifestHash'],'sourceFingerprint':manifest['sourceFingerprint'],'files':files,'analysis':analysis,'expectedSamples':[],'timeoutSeconds':timeout,'measurementDeclarations':declared,'expectedMeasurements':expected_measurements}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Native measurement plan exceeds durable bound.')
            self.preflight(payload);return self.create_plan(payload)

    def preflight(self,p):
        super().preflight(p)
        texts={f['relativePath']:(Path(p['preparedDirectory'])/f['relativePath']).read_text(encoding='utf-8') for f in p['files']}
        for text in texts.values():execution_preflight(text)
        declared=declarations(texts,p['analysis'])
        if p['expectedSamples'] or declared!=p['measurementDeclarations'] or not valid_expectations(p['expectedMeasurements'],{r['name'].casefold() for r in declared}):raise CadenceError('invalid_plan','Native measurement declarations or expectations differ from the prepared closure.')

    def preview(self,p):
        return {**super().preview(p),'backend':'independent_pspice_complete_analysis','measurementDeclarations':p['measurementDeclarations'],'expectedMeasurements':p['expectedMeasurements'],'acceptanceScope':'declared_native_measurement_fields_only'}

    def native_command(self,d,p):
        return [str(x) for x in (self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_measure.tcl',self.config.install_root,d/'input.cir',d)]

    def confirm_receipt(self,d,p):
        path=checked_path(str(d/'receipt.json'),(d,))
        if path.stat().st_size>4096:raise CadenceError('invalid_worker_result','Native measurement receipt exceeds bound.')
        receipt=json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('entryPoint')!='PSpiceDoAnalysis' or type(receipt.get('caught')) is not int or receipt['caught']!=0 or receipt.get('analysisReturn')!='0' or receipt.get('cleanupReturn')!='0':raise CadenceError('pspice_engine_failed','Complete native analysis did not confirm success.')

    def confirm_output(self,text,p):
        if 'JOB CONCLUDED' not in text or 'JOB STATISTICS SUMMARY' not in text:raise CadenceError('incomplete_simulation_output','Native complete-analysis output has no completion markers.')

    def extra_artifacts(self,d,p):
        path=checked_path(str(d/'input_measure.txt'),(d,))
        if path.stat().st_size>1024*1024:raise CadenceError('measurement_limit','Native measurement file exceeds1MiB.')
        before=sha256(path);rows=parse_measurements(path.read_text(encoding='cp1252'));byname={r['name'].casefold():r for r in rows}
        if set(byname)!={r['name'].casefold() for r in p['measurementDeclarations']}:raise CadenceError('measurement_declaration_mismatch','Native result names differ from the frozen declarations.')
        if any(r['state']!='evaluated' for r in rows):raise CadenceError('native_measurement_failed','Native measurement reports Evaluation Failed; no numeric result certified.')
        checks=[]
        for expected in p['expectedMeasurements']:
            actual=byname[expected['name'].casefold()]['fields'].get(expected['field'])
            if actual is None or abs(actual-expected['expected'])>expected['absoluteTolerance']+expected['relativeTolerance']*abs(expected['expected']):raise CadenceError('measurement_expectation_mismatch','A native measurement field differs from its independent expectation.')
            checks.append({**expected,'observed':actual})
        if sha256(path)!=before:raise CadenceError('target_changed','Native measurement bytes changed during verification.')
        return [{'relativePath':path.name,'sha256':before,'size':path.stat().st_size}],{'nativeMeasurements':rows,'nativeMeasurementChecks':checks,'nativeMeasurementIdentityVerified':True}

    def output_names(self):return (*super().output_names(),'input_measure.txt')

    def inspect_measurements(self,plan_id,plan_digest):
        guard=self._guard()
        try:
            d,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified native measurement runs can be inspected.')
            result=self._verified_result(d,row)
            manifest=json.loads((d/'run-artifacts.json').read_text(encoding='utf-8'))
            payload=row['plan']['payload'];hashes={f['relativePath']:f['sha256'] for f in manifest['files']};texts=[]
            for item in payload['files']:
                path=checked_path(str(d/item['relativePath']),(d,));raw=path.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=hashes.get(item['relativePath']) or sha256(path)!=hashes[item['relativePath']]:raise CadenceError('target_changed','Verified measurement input changed during unit annotation.')
                texts.append(raw.decode('utf-8',errors='strict'))
            measurements,units=annotate_measurements(manifest['nativeMeasurements'],payload['measurementDeclarations'],payload['analysis'],texts)
            self._verified_result(d,row)
            return {'planId':plan_id,'nativeCompletionVerified':result['nativeCompletionVerified'],'jobAssociationVerified':True,'nativeMeasurements':measurements,'measurementUnits':units,'nativeMeasurementChecks':manifest['nativeMeasurementChecks'],'numericalAcceptanceScope':result['numericalAcceptanceScope'],'designPassed':None,'runManifestSha256':result['artifact']['sha256']}
        finally:guard.close()
