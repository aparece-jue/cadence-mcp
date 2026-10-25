"""Official noninteractive psp_cmd /r over the established frozen-run contract."""
import json
from .core import CadenceError,checked_path,sha256,write_json
from .pspice_runs import PSpiceRuns,ANALYSES
from .pspice_output import parse_out
from .pspice_diagnostics import failure_for_output

class PSpiceCliRuns(PSpiceRuns):
    kind='pspice_cli_run'
    def backend_name(self):return 'official_psp_cmd_r'
    def extra_scope(self):return 'declared_trace_rows_only'
    def backend_not_checked(self):return []
    def plan(self,simulation_id,analysis,expected_samples=None,timeout_seconds=None):
        with self.inputs.lock:
            self.inputs.get(simulation_id)
            if analysis in ANALYSES and self.inputs.inputs[simulation_id]['manifest']['analyses']!=[ANALYSES[analysis][0]]:
                raise CadenceError('unsupported_cli_analyses','Official /r executes all CIR analyses; declare exactly one selected analysis type.')
            return super().plan(simulation_id,analysis,expected_samples,timeout_seconds)
    def native_command(self,d,p):return [str(self.config.install_root/'tools/bin/psp_cmd.exe'),'/r',str(d/'input.cir')]

    def execute(self,d,p,cancel,on_started):
        for name in ('input.out','input.dat','result.out','result.dat','cli-receipt.json','run-artifacts.json'):
            if (d/name).exists() or (d/name).is_symlink():
                raise CadenceError('preexisting_cli_output','Owned CLI job contains an output before execution; retain it without running or overwriting.')
        process=super().execute(d,p,cancel,on_started)
        if process['state']!='exited':return process
        hashes={}
        for raw,canonical in (('input.out','result.out'),('input.dat','result.dat')):
            if not (d/raw).exists():hashes[raw]=None;continue
            source=checked_path(str(d/raw),(d,))
            if source.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Native CLI output exceeds32MiB.')
            before=sha256(source);payload=source.read_bytes()
            if len(payload)>32*1024*1024 or sha256(source)!=before:raise CadenceError('target_changed','CLI output changed while copying.')
            with (d/canonical).open('xb') as stream:stream.write(payload)
            if sha256(d/canonical)!=before:raise CadenceError('target_changed','Canonical CLI output differs from native bytes.')
            hashes[raw]=before
        write_json(d/'cli-receipt.json',{'command':['psp_cmd.exe','/r','input.cir'],
                   'jobInputSha256':sha256(d/'input.cir'),'nativeHashes':hashes,
                   **{k:process[k] for k in ('returnCode','remainingOwnedProcesses','rootExitSignalConfirmed','observedProcessExitSignalsConfirmed')}})
        return process

    def confirm_receipt(self,d,p):
        path=checked_path(str(d/'cli-receipt.json'),(d,))
        if path.stat().st_size>4096:raise CadenceError('invalid_worker_result','CLI receipt exceeds bound.')
        receipt=json.loads(path.read_text(encoding='utf-8'))
        if (receipt.get('command')!=['psp_cmd.exe','/r','input.cir']
            or type(receipt.get('returnCode')) is not int or receipt['returnCode']!=0
            or type(receipt.get('remainingOwnedProcesses')) is not int or receipt['remainingOwnedProcesses']!=0
            or receipt.get('rootExitSignalConfirmed') is not True or receipt.get('observedProcessExitSignalsConfirmed') is not True
            or receipt.get('jobInputSha256')!=sha256(checked_path(str(d/'input.cir'),(d,)))):
            raise CadenceError('pspice_cli_failed','CLI completion/owned-process/input receipt is not valid.')
        expected={name:sha256(checked_path(str(d/name),(d,))) for name in ('input.out','input.dat')}
        if receipt.get('nativeHashes')!=expected:raise CadenceError('target_changed','Native CLI output differs from its completion receipt.')

    def confirm_output(self,text,p):
        if 'JOB CONCLUDED' not in text or 'JOB STATISTICS SUMMARY' not in text:raise CadenceError('incomplete_simulation_output','CLI OUT lacks its completion markers.')

    def extra_artifacts(self,d,p):
        files=[]
        for raw,canonical in (('input.out','result.out'),('input.dat','result.dat')):
            native=checked_path(str(d/raw),(d,));target=checked_path(str(d/canonical),(d,))
            if native.stat().st_size>32*1024*1024 or sha256(native)!=sha256(target):raise CadenceError('target_changed','Native and canonical CLI bytes differ.')
            files.append({'relativePath':raw,'sha256':sha256(native),'size':native.stat().st_size})
        if (d/'cli-receipt.json').exists():
            self.confirm_receipt(d,p);receipt=checked_path(str(d/'cli-receipt.json'),(d,))
            files.append({'relativePath':receipt.name,'sha256':sha256(receipt),'size':receipt.stat().st_size})
        return files,{'cliCommandMode':'psp_cmd /r','nativeOutputIdentityVerified':True}

    def verify(self,d,p,native_completed):
        # CLI may exit0 with an error and no DAT; classify that OUT before any success checks.
        if (d/'result.out').exists():
            out=checked_path(str(d/'result.out'),(d,))
            if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','CLI OUT exceeds bound.')
            parsed=parse_out(out.read_text(encoding='cp1252'))
            if parsed['hasErrorDiagnostics']:raise failure_for_output(parsed)
        return super().verify(d,p,native_completed)

    def worker_error(self,d,p,process):
        error=super().worker_error(d,p,process)
        if error.code=='pspice_engine_failed':return CadenceError('pspice_cli_failed','Official CLI returned a failure; inspect retained owned outputs.','solver')
        return error

    def output_names(self):return (*super().output_names(),'input.out','input.dat','cli-receipt.json')
