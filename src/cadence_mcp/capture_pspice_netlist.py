"""Persistent fixed native NET/ALS jobs over a frozen project and authenticated host."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
from .core import CadenceError,checked_path,sha256,write_json
from .isolated_jobs import IsolatedJobs
from .gui_jobs import acquire_guard
from .bridge_rpc import RpcConnection,process_image
from .gui_readiness import require_write_ready
from .capture_pspice_project import freeze_project,validate_snapshot,stage_snapshot
from .capture_pspice_receipt import validate_envelope,decode_receipt
from .native_host_fence import ensure_idle,claim,release,read_fence
from .environment import ADAPTERS,process_env
from .gui_loader import tcl_string
from .process_tree import run_owned_process

def _write_dispatch_files(directory, code):
    """Capture replays command files; source a complete Tcl script as one command."""
    payload=directory/'payload.tcl'
    wrapper=directory/'invoke.tcl'
    with payload.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(code)
    with wrapper.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('source '+tcl_string(payload.as_posix())+'\n')
    return wrapper

class CapturePSpiceNetlists(IsolatedJobs):
    kind='capture_pspice_netlist'
    max_record_bytes=65536
    def __init__(self,config,capture,gui):
        super().__init__(config);self.capture=capture;self.gui=gui

    def plan(self,session_id,gui_session_id,source_project,source_profile):
        with self.gui.lock:
            if gui_session_id not in self.gui.sessions:raise CadenceError('session_lost','Attach an explicit GUI host session.')
            session=self.gui.sessions[gui_session_id];binding=session['connection'].path.resolve(strict=True)
            raw=json.loads(binding.read_text(encoding='utf-8'));hello=session['connection'].call('hello',{})
            host={'bindingPath':str(binding),'bindingSha256':sha256(binding),'pid':session['pid'],
                  'instanceId':session['instanceId'],'generation':session['generation'],'sessionId':gui_session_id,
                  'activeDesign':str(Path(raw['expectedDesign']).resolve(strict=True)),
                  'activeFingerprint':raw['sourceFingerprint'],'executableFingerprint':raw['executableFingerprint']}
            if hello['generation']!=host['generation']:raise CadenceError('session_lost','Host generation changed; explicitly attach again.')
        snapshot=freeze_project(self.config,self.capture,session_id,source_project,source_profile)
        payload={'snapshot':snapshot,'host':host,'adapterHashes':{name:sha256(ADAPTERS/name) for name in ['json.tcl','capture_pspice_netlist_job.tcl']}}
        if len(json.dumps(payload).encode('utf-8'))>49152:raise CadenceError('plan_limit','Native export plan exceeds its durable bound.')
        self.preflight(payload);return self.create_plan(payload)

    def preview(self,p):
        d=p['snapshot']['description'];return {'scope':d['scope'],'projectName':d['projectTarget'],
                'rootName':d['rootName'],'profileName':d['profileName'],'designRevision':p['snapshot']['sources'][0]['sha256'],
                'hostInstanceId':p['host']['instanceId'],'hostPid':p['host']['pid'],
                'sourceWillBeModified':False,'guiProjectSwitchRequested':False,'cancelScope':'pending_only',
                'completionBasis':'native_pid_nonce_receipt_and_bound_artifacts','modelDependenciesVerified':False}

    def _binding(self,p):
        path=Path(p['host']['bindingPath']).resolve(strict=True)
        registered=set()
        for candidate in self.gui.configs:
            try:registered.add(Path(candidate).resolve(strict=True))
            except OSError:continue
        for root in self.gui.roots:
            registered.update(x.resolve(strict=True) for x in Path(root).glob('gui-bridge-*/binding.json'))
        if path not in registered:raise CadenceError('instance_not_found','Frozen host binding is no longer registered.')
        return path

    def _context(self,p,require_session=True):
        host=p['host'];binding=self._binding(p)
        if sha256(binding)!=host['bindingSha256']:raise CadenceError('instance_replaced','Frozen binding changed; no automatic retargeting.')
        exe=(self.config.install_root/'tools/bin/Capture.exe').resolve(strict=True)
        if process_image(host['pid'])!=exe or sha256(exe)!=host['executableFingerprint']:raise CadenceError('instance_replaced','Actual Capture process/executable differs from the frozen host.')
        rpc=RpcConnection(binding);reply=rpc.call('hello',{});data=reply['data']
        if reply['pid']!=host['pid'] or reply['instanceId']!=host['instanceId'] or reply['generation']!=host['generation']:
            raise CadenceError('instance_replaced','Host instance/generation changed.')
        if data['bindingLost'] or data['dirtyState']!='clean' or data['propertyPlanCount']!=0 or sha256(Path(host['activeDesign']))!=host['activeFingerprint']:
            raise CadenceError('bridge_busy','Host must retain its clean frozen design and have no unresolved metadata plans.')
        if 'native_netlist_fence_v1' not in data['capabilities']:raise CadenceError('capability_unavailable','Reload the trusted bridge with native host fencing before planning export.')
        if require_session:rpc.call('status',{'sessionId':host['sessionId'],'generation':host['generation']})
        return binding

    def preflight(self,p):
        if not isinstance(p,dict) or set(p)!={'snapshot','host','adapterHashes'}:raise CadenceError('invalid_plan','Invalid native export payload.')
        validate_snapshot(self.config,p['snapshot'])
        if p['adapterHashes']!={name:sha256(ADAPTERS/name) for name in ['json.tcl','capture_pspice_netlist_job.tcl']}:
            raise CadenceError('target_changed','Native adapter changed after planning.')
        ensure_idle(self._binding(p));binding=self._context(p);require_write_ready(p['host']['pid'])

    def _lease(self,d,p):
        return {'kind':'native_netlist_v1','jobId':d.name.removeprefix('plan-'),'pid':p['host']['pid'],
                'instanceId':p['host']['instanceId'],'jobDirectory':str(d),'bindingSha256':p['host']['bindingSha256']}

    def _read(self,path):
        path=checked_path(str(path),(self.config.workspace_root,))
        if path.stat().st_size>1048576:raise CadenceError('invalid_native_receipt','Native receipt/manifest exceeds one MiB.')
        try:return json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError) as error:raise CadenceError('invalid_native_receipt','Native receipt/manifest is not complete JSON.') from error

    def _completion(self,d,p):
        nonce=d.name.removeprefix('plan-');receipt=d/'native-result.json';rejected=d/'dispatch-rejected.json'
        if receipt.exists():return 'receipt',validate_envelope(self._read(receipt),nonce,p['host']['pid'])
        if rejected.exists():
            raw=self._read(rejected)
            if (set(raw)!={'jobId','pid','rejectedBeforeNative','reason'} or raw['jobId']!=nonce or type(raw['pid']) is not int
                or raw['pid']!=p['host']['pid'] or raw['rejectedBeforeNative'] is not True
                or raw['reason'] not in ('bridge_busy','wrong_active_design','output_exists') or (d/'entered.txt').exists()):
                raise CadenceError('invalid_native_receipt','Dispatch refusal is not a proven pre-native rejection.')
            return 'rejected',raw
        return None,None

    def _wait_completion(self,d,p):
        until=time.monotonic()+min(30,self.config.timeout_seconds)
        while time.monotonic()<until:
            kind,raw=self._completion(d,p)
            if kind:return kind,raw
            time.sleep(.1)
        raise CadenceError('native_completion_unknown','No host completion/refusal receipt arrived; fence retained. Never resend this task.','worker')

    def _observe_after(self,d,p,recovery=False):
        if (d/'host-after.json').exists():return
        preserved=False
        try:self._context(p,require_session=not recovery);preserved=True
        except (CadenceError,OSError):pass
        write_json(d/'host-after.json',{'jobId':d.name.removeprefix('plan-'),'pid':p['host']['pid'],
                   'bindingSha256':p['host']['bindingSha256'],'activeFingerprint':p['host']['activeFingerprint'],
                   'preserved':preserved,'observation':'recovery' if recovery else 'after_native_return'})

    def execute(self,d,p,cancel,on_started):
        binding=self._binding(p);guard=acquire_guard(binding.parent);owner=self._lease(d,p);completed=False
        try:
            self.preflight(p)
            if cancel is not None and cancel.is_set():return {'state':'cancelled','pid':None,'returnCode':None,'remainingOwnedProcesses':0}
            if {x.name for x in d.iterdir()}!={'plan.json'}:raise CadenceError('preexisting_native_output','Fresh native task contains unexpected preexisting files.')
            paths=stage_snapshot(self.config,p['snapshot'],d);description=p['snapshot']['description']
            write_json(d/'staged-inputs.json',{'paths':paths,'hashes':{role:sha256(Path(path)) for role,path in paths.items()}})
            target=d/'project'/description['netlistTarget'];nonce=owner['jobId'];host=p['host']
            args=[str(host['pid']),host['activeDesign'],paths['design'],target.as_posix(),(d/'native-result.json').as_posix(),
                  (d/'entered.txt').as_posix(),nonce,(self.config.install_root/'tools/bin/orTclNetlist64.dll').as_posix()]
            invocation='::cmcpNativeNetlist::run '+' '.join(tcl_string(x) for x in args)
            code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'capture_pspice_netlist_job.tcl').as_posix())+'\n'
            code+='set caught [catch {'+invocation+'} message]\n'
            code+='if {$caught && [pid]=='+str(host['pid'])+' && ![file exists '+tcl_string((d/'entered.txt').as_posix())+'] && $message in {bridge_busy wrong_active_design output_exists}} {\n'
            code+='set f [open '+tcl_string((d/'dispatch-rejected.json').as_posix())+' {WRONLY CREAT EXCL}];puts $f [cmcp::obj jobId '+tcl_string(nonce)+' pid [pid] rejectedBeforeNative true reason [cmcp::q $message]];close $f\n}\n'
            wrapper=_write_dispatch_files(d,code)
            claim(binding,owner);write_json(d/'dispatch-claim.json',owner)
            process=run_owned_process([str(self.config.install_root/'tools/bin/Capture.exe'),str(wrapper)],d,process_env(self.config),min(10,self.config.timeout_seconds),on_started=on_started)
            write_json(d/'forwarder.json',process)
            if process['state']!='exited' or process['returnCode']!=0:
                raise CadenceError('native_completion_unknown','Forwarder did not finish normally; it cannot prove whether Capture ran the task. Fence retained.','worker')
            kind,raw=self._wait_completion(d,p);completed=True
            if kind=='rejected':raise CadenceError('native_dispatch_refused','Host rejected this task before the native operation; preserve its refusal receipt.','worker')
            self._observe_after(d,p)
            return process
        finally:
            if completed:release(binding,owner)
            guard.close()

    def verify(self,d,p,native_completed):
        kind,raw=self._completion(d,p)
        if not kind:raise CadenceError('native_completion_unknown','No valid native completion receipt; original operation is not replayable.','verify')
        binding=self._binding(p);guard=acquire_guard(binding.parent)
        try:
            release(binding,self._lease(d,p))
            if kind=='rejected':raise CadenceError('native_dispatch_refused','Native task was refused before execution.','verify')
            native=decode_receipt(raw,d.name.removeprefix('plan-'),p['host']['pid']);self._observe_after(d,p,recovery=not native_completed)
        finally:guard.close()
        after=self._read(d/'host-after.json')
        if (after.get('jobId')!=d.name.removeprefix('plan-') or after.get('pid')!=p['host']['pid']
                or after.get('bindingSha256')!=p['host']['bindingSha256'] or after.get('activeFingerprint')!=p['host']['activeFingerprint'] or after.get('preserved') is not True):
            raise CadenceError('host_context_changed','Frozen active host context was not preserved; outputs remain unaccepted.','verify')
        staged=self._read(d/'staged-inputs.json');description=p['snapshot']['description'];artifacts=[]
        for role in ('project','design','profile'):
            relative='project/'+description[role+'Target'];path=checked_path(str(d/relative),(d,))
            wanted=description['stagedProjectSha256'] if role=='project' else next(x['sha256'] for x in p['snapshot']['sources'] if x['role']==role)
            if str(path)!=str(Path(staged['paths'][role]).resolve()) or sha256(path)!=wanted or staged['hashes'][role]!=wanted:
                raise CadenceError('target_changed','Native task staged inputs changed.','verify')
            artifacts.append({'relativePath':relative,'sha256':wanted,'size':path.stat().st_size})
        for relative in ['project/'+description['netlistTarget'],'project/'+description['aliasesTarget'],'native-result.json','host-after.json','staged-inputs.json','dispatch-claim.json','entered.txt','payload.tcl','invoke.tcl','forwarder.json']:
            path=checked_path(str(d/relative),(d,))
            if not path.is_file() or not 0<path.stat().st_size<=32*1024*1024:raise CadenceError('invalid_native_output','Native task output is empty, absent or oversized.','verify')
            artifacts.append({'relativePath':relative,'sha256':sha256(path),'size':path.stat().st_size})
        if (d/'entered.txt').read_text(encoding='utf-8').strip()!=d.name.removeprefix('plan-'):raise CadenceError('invalid_native_receipt','Native entry marker does not match its task.')
        if self._read(d/'dispatch-claim.json')!=self._lease(d,p):raise CadenceError('invalid_native_receipt','Frozen dispatch claim differs from its host/task.')
        manifest={'kind':self.kind,'sourceDesignRevision':p['snapshot']['sources'][0]['sha256'],'files':artifacts,'native':native,'modelsVerified':False,'solverRun':False}
        target=d/'netlist-artifacts.json'
        if target.exists():
            if self._read(target)!=manifest:raise CadenceError('target_changed','Native artifact manifest differs from the existing task.')
        else:write_json(target,manifest)
        return {'outputWorkspaceRelativePath':str(d.relative_to(self.config.workspace_root)),
                'artifact':self._artifact(d,manifest),
                'netlistRelativePath':'project/'+description['netlistTarget'],'aliasesRelativePath':'project/'+description['aliasesTarget'],
                'sourceDesignRevision':manifest['sourceDesignRevision'],'nativeCompletionVerified':True,'sourceModified':False,
                'guiProjectSwitchRequested':False,'hostContextPreserved':True,'modelDependenciesVerified':False,'solverRun':False,
                'scope':description['scope'],'notChecked':['drc','complete_hierarchy_model_closure','solver','numerical_results']}

    def _artifact(self,d,manifest):
        target=d/'netlist-artifacts.json'
        created=self._read(d/'plan.json')['plan']['createdAt']
        ident=d.name.removeprefix('plan-')
        return {'artifactId':'native-netlist-'+ident,'kind':'capture_pspice_netlist_manifest',
                'workspaceRelativePath':'netlist-artifacts.json','sha256':sha256(target),'size':target.stat().st_size,
                'producedByJob':ident,'sourceFingerprint':manifest['sourceDesignRevision'],
                'sourceKind':'file_fingerprint','createdAt':datetime.fromtimestamp(created,timezone.utc).isoformat(),
                'validationState':'validated'}

    def _verified_result(self,d,row):
        result=super()._verified_result(d,row);manifest=self._read(d/'netlist-artifacts.json')
        for file in manifest['files']:
            path=checked_path(str(d/file['relativePath']),(d,))
            if sha256(path)!=file['sha256']:raise CadenceError('target_changed','Previously verified native task file changed.')
        # Internal component jobs recorded before MCP registration used a minimal artifact.
        # Reconstruct metadata only after every recorded artifact hash was checked above.
        if set(result['artifact'])=={'workspaceRelativePath','sha256'}:
            result={**result,'artifact':self._artifact(d,manifest)}
        return result

    def cancel(self,plan_id,plan_digest):
        d,path,row=self._load(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest does not match.')
        if row['state']=='started':raise CadenceError('too_late','A started host task cannot be cancelled by killing Capture or its forwarder; observe/recover only.')
        return super().cancel(plan_id,plan_digest)
