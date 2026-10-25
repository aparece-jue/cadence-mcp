"""Read-only observations of stopped failed owned jobs; never promote them to success."""
import hashlib,json
from .core import CadenceError,checked_path,sha256
from .bridge_diagnostics import process_status
from .pspice_output import parse_out

def inspect_failure(service,plan_id,plan_digest):
    guard=service._guard()
    try:
        directory,_,row=service._load(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
        if row['state'] not in ('failed','cancelled'):raise CadenceError('failure_inspection_unavailable','Inspect only terminal failed/cancelled jobs; successful jobs use their verified artifact tools.')
        pid=row.get('workerPid')
        if pid is not None and process_status(pid)!='stopped':raise CadenceError('process_state_unknown','Failure inspection requires proof the original worker is stopped.')
        if pid is None and row.get('startedAt') is not None:raise CadenceError('process_state_unknown','Started job has no independently stopped worker identity.')
        snapshots={};parsed=None;parse_error=None;receipt=None
        for name,bound in (('result.out',32*1024*1024),('receipt.json',4096)):
            if not (directory/name).exists():continue
            path=checked_path(str(directory/name),(directory,))
            if path.stat().st_size>bound:raise CadenceError('output_limit','Failure artifact exceeds its fixed bound.')
            before=sha256(path);raw=path.read_bytes()
            if len(raw)>bound or hashlib.sha256(raw).hexdigest()!=before:raise CadenceError('target_changed','Failure bytes changed while reading.')
            snapshots[name]={'sha256':before,'size':len(raw)}
            if name=='result.out':
                try:parsed=parse_out(raw.decode('cp1252'))
                except CadenceError as error:parse_error=error.code
                except UnicodeError:parse_error='unsupported_encoding'
            else:
                try:receipt=json.loads(raw.decode('utf-8'))
                except (ValueError,UnicodeError):parse_error=parse_error or 'invalid_worker_receipt'
        input_match=False;input_error=None
        try:
            service.preflight(row['plan']['payload'])
            expected=service.rebased_inputs(directory,row['plan']['payload'])
            input_match=all(checked_path(str(directory/name),(directory,)).read_bytes()==raw for name,raw in expected.items())
        except (CadenceError,OSError) as error:input_error=getattr(error,'code','input_unavailable')
        for name,record in snapshots.items():
            if sha256(checked_path(str(directory/name),(directory,)))!=record['sha256']:raise CadenceError('target_changed','Failure artifact changed during inspection.')
        return {'planId':plan_id,'state':row['state'],'kind':row['plan']['kind'],
                'provenance':'failed_job_observation','jobDirectoryAssociationVerified':True,
                'sourceFingerprint':row['plan']['payload']['sourceFingerprint'],
                'workerStoppedVerified':pid is not None,'workerNotStarted':pid is None,
                'inputClosureMatchesPlan':input_match,'inputVerificationError':input_error,
                'recordedError':row.get('error'),'process':row.get('process'),'observedFiles':snapshots,
                'output':parsed,'parseError':parse_error,'receipt':receipt,
                'solverSuccessVerified':False,'nativeCompletionVerified':False,'numericalAcceptanceVerified':False,
                'designPassed':None,'canReplayMutation':False,
                'notChecked':['complete_error_grammar','license_server_health','electrical_design_safety']}
    finally:guard.close()
