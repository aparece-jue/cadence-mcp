"""Bound editor execution for existing wire-add jobs; never edits the source."""
import json,re,shutil,time
from pathlib import Path
from .core import CadenceError,checked_path,sha256,write_json
from .bridge_rpc import RpcConnection,process_image
from .gui_readiness import require_write_ready
from .gui_jobs import acquire_guard
from .native_host_fence import ensure_idle,claim,release
from .gui_loader import tcl_string
from .environment import ADAPTERS,process_env
from .process_tree import run_owned_process

ADAPTER_NAMES=('json.tcl','editor_wire_add_job.tcl','editor_wire_delete_job.tcl')

class EditorWireHost:
    adapter_names=ADAPTER_NAMES
    def __init__(self,config,gui):self.config,self.gui=config,gui

    def binding(self,h):
        path=Path(h['bindingPath']).resolve(strict=True);registered=set()
        if self.gui is None:raise CadenceError('instance_not_found','No GUI bindings configured.')
        for p in self.gui.configs:
            if Path(p).exists():registered.add(Path(p).resolve(strict=True))
        for root in self.gui.roots:registered.update(p.resolve(strict=True) for p in Path(root).glob('gui-bridge-*/binding.json'))
        if path not in registered:raise CadenceError('instance_not_found','Frozen editor binding is not registered.')
        if sha256(path)!=h['bindingSha256']:raise CadenceError('instance_replaced','Editor binding changed after planning.')
        return path

    def freeze(self,sid,host_project):
        if self.gui is None:raise CadenceError('instance_not_found','Configure a GUI host for editor wire addition.')
        with self.gui.lock:
            if sid not in self.gui.sessions:raise CadenceError('session_lost','Attach an explicit GUI session first.')
            s=self.gui.sessions[sid];binding=s['connection'].path.resolve(strict=True)
            b=json.loads(binding.read_text(encoding='utf-8'))
            project=checked_path(host_project,(*self.config.read_roots,self.config.workspace_root))
            active=checked_path(b['expectedDesign'],(*self.config.read_roots,self.config.workspace_root))
            if active.is_relative_to(self.config.install_root) or project.parent!=active.parent or project.stem.lower()!=active.stem.lower() or project.suffix.lower()!='.opj':
                raise CadenceError('unsupported_editor_host','Host project must be the explicit same-stem private PCB project of the bound design.')
            if project.stat().st_size>1048576:raise CadenceError('unsupported_editor_host','Host project exceeds one MiB.')
            text=project.read_text(encoding='utf-8')
            files=re.findall(r'\(File\s+"([^"\r\n]+)"\s+\(Type\s+"Schematic Design"\)\)',text)
            if '(ProjectType "PCB")' not in text or len(files)!=1 or len(re.findall(r'\(File\s',text))!=1 or (project.parent/files[0].replace('\\','/')).resolve()!=active:
                raise CadenceError('unsupported_editor_host','Use a single-design PCB control project; other host resources need separate validation.')
            h={'bindingPath':str(binding),'bindingSha256':sha256(binding),'pid':s['pid'],'instanceId':s['instanceId'],
               'generation':s['generation'],'sessionId':sid,'activeDesign':str(active),'activeFingerprint':b['sourceFingerprint'],
               'hostProject':str(project),'hostProjectSha256':sha256(project),'executableFingerprint':b['executableFingerprint'],
               'adapterHashes':{name:sha256(ADAPTERS/name) for name in self.adapter_names}}
            self.context(h,True);return h

    def static(self,h):
        self.binding(h)
        for path,key in [('activeDesign','activeFingerprint'),('hostProject','hostProjectSha256')]:
            if sha256(Path(h[path]))!=h[key]:raise CadenceError('target_changed','Frozen editor host files changed.')
        if h['adapterHashes']!={name:sha256(ADAPTERS/name) for name in self.adapter_names}:raise CadenceError('target_changed','Fixed editor adapter changed.')

    def context(self,h,before):
        self.static(h);exe=(self.config.install_root/'tools/bin/Capture.exe').resolve(strict=True)
        if process_image(h['pid'])!=exe or sha256(exe)!=h['executableFingerprint']:raise CadenceError('instance_replaced','Editor host process differs from the frozen host.')
        reply=RpcConnection(self.binding(h)).call('hello',{});data=reply['data']
        if reply['pid']!=h['pid'] or reply['instanceId']!=h['instanceId'] or data['bindingLost'] or data['dirtyState']!='clean' or data['propertyPlanCount']!=0:
            raise CadenceError('bridge_busy','Editor requires the original clean bound host with no metadata plans.')
        if before:
            if reply['generation']!=h['generation']:raise CadenceError('session_lost','Explicitly attach a new GUI session.')
            RpcConnection(self.binding(h)).call('status',{'sessionId':h['sessionId'],'generation':h['generation']})
            ensure_idle(self.binding(h));require_write_ready(h['pid'])
        elif reply['generation']<=h['generation']:raise CadenceError('invalid_native_receipt','Expected explicit old-session invalidation was not observed.')
        return reply['generation']

    def owner(self,d,h):return {'kind':'native_netlist_v1','jobId':d.name.removeprefix('plan-'),'pid':h['pid'],'instanceId':h['instanceId'],'jobDirectory':str(d),'bindingSha256':h['bindingSha256']}

    def receipt(self,d,h):
        path=checked_path(str(d/'native-result.json'),(d,))
        if path.stat().st_size>8192:raise CadenceError('invalid_native_receipt','Editor receipt exceeds its bound.')
        try:row=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError) as error:raise CadenceError('invalid_native_receipt','Editor receipt is incomplete.') from error
        if (set(row)!={'jobId','pid','saved','hostRestored','invocationReturned','phase','error'} or row['jobId']!=d.name.removeprefix('plan-') or type(row['pid']) is not int or row['pid']!=h['pid'] or any(type(row[k]) is not bool for k in ('saved','hostRestored','invocationReturned'))):
            raise CadenceError('invalid_native_receipt','Editor task receipt identity/shape differs.')
        if (d/'entered.txt').read_text(encoding='utf-8').strip()!=row['jobId']:raise CadenceError('invalid_native_receipt','Editor entry marker differs.')
        return row

    def observe(self,d,h):
        path=d/'host-after.json'
        if not path.exists():
            generation=self.context(h,False)
            write_json(path,{'jobId':d.name.removeprefix('plan-'),'pid':h['pid'],'bindingSha256':h['bindingSha256'],'activeFingerprint':h['activeFingerprint'],'hostProjectSha256':h['hostProjectSha256'],'generation':generation,'preserved':True})
        row=json.loads(path.read_text(encoding='utf-8'))
        if (row.get('jobId')!=d.name.removeprefix('plan-') or row.get('pid')!=h['pid'] or row.get('bindingSha256')!=h['bindingSha256'] or row.get('activeFingerprint')!=h['activeFingerprint'] or row.get('hostProjectSha256')!=h['hostProjectSha256'] or row.get('preserved') is not True or type(row.get('generation')) is not int or row['generation']<=h['generation']):
            raise CadenceError('host_context_changed','No matching restored-host observation exists.')

    def invocation(self,d,p,project,target,owner):
        h=p['editorHost']
        deleting=p.get('operation')=='delete'
        points=p['oldPoints'] if deleting else [p['start'],p['end']]
        net=p['oldNet'] if deleting else p['netName'];anchor=[0,0] if deleting else p['aliasLocation']
        args=[h['pid'],h['activeDesign'],h['hostProject'],project.as_posix(),target.as_posix(),p['schematicName'],p['pageName'],p.get('editorOccurrence') or '',*points[0],*points[1],net,*anchor,(d/'native-result.json').as_posix(),(d/'entered.txt').as_posix(),owner['jobId']]
        if deleting:args.append(json.dumps(p['aliases'],ensure_ascii=False))
        adapter='editor_wire_delete_job.tcl' if deleting else 'editor_wire_add_job.tcl'
        command='::cmcpEditorDelete::run' if deleting else '::cmcpEditorWire::run'
        return adapter,command,args

    def execute(self,d,p,cancel,on_started):
        h=p['editorHost'];binding=self.binding(h);guard=acquire_guard(binding.parent);owner=self.owner(d,h)
        try:
            self.context(h,True)
            if cancel is not None and cancel.is_set():return {'state':'cancelled','pid':None,'returnCode':None,'remainingOwnedProcesses':0}
            if {f.name for f in d.iterdir()}!={'plan.json'}:raise CadenceError('output_exists','Editor tasks require a new output directory.')
            source=Path(p['sourceDesign']);target=d/'design.dsn'
            with source.open('rb') as src,target.open('xb') as out:shutil.copyfileobj(src,out)
            if sha256(source)!=p['sourceFingerprint'] or sha256(target)!=p['sourceFingerprint']:raise CadenceError('target_changed','Source changed while staging editor output.')
            project=d/'editor-output.opj'
            with project.open('x',encoding='utf-8') as stream:stream.write('(ExpressProject "editor-output"\n (ProjectVersion "19981106")\n (SoftwareVersion "24.1")\n (ProjectType "PCB")\n (Folder "Design Resources" (Folder "Library") (NoModify) (File "./design.dsn" (Type "Schematic Design")))\n)\n')
            adapter,command,args=self.invocation(d,p,project,target,owner)
            code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/adapter).as_posix())+'\n'+command+' '+' '.join(tcl_string(a) for a in args)+'\n'
            with (d/'payload.tcl').open('x',encoding='utf-8') as stream:stream.write(code)
            with (d/'invoke.tcl').open('x',encoding='utf-8') as stream:stream.write('source '+tcl_string((d/'payload.tcl').as_posix())+'\n')
            claim(binding,owner);write_json(d/'dispatch-claim.json',owner)
            process=run_owned_process([self.config.install_root/'tools/bin/Capture.exe',d/'invoke.tcl'],d,process_env(self.config),min(10,self.config.timeout_seconds),on_started=on_started)
            write_json(d/'forwarder.json',process)
            until=time.monotonic()+min(30,self.config.timeout_seconds)
            while not (d/'native-result.json').exists() and time.monotonic()<until:time.sleep(.1)
            if not (d/'native-result.json').exists():raise CadenceError('native_completion_unknown','Editor outcome unknown; fence retained, never replay this job.')
            self.complete(d,h)
            if process['state']!='exited' or process['returnCode']!=0:raise CadenceError('native_completion_unknown','Forwarder outcome uncertain; inspect/recover the receipt without replay.')
            return process
        finally:guard.close()

    def complete(self,d,h):
        row=self.receipt(d,h)
        if not row['hostRestored']:raise CadenceError('host_context_changed','Editor did not restore the host; fence retained, no automatic close or replay.')
        self.observe(d,h)
        if json.loads((d/'dispatch-claim.json').read_text(encoding='utf-8'))!=self.owner(d,h):raise CadenceError('invalid_native_receipt','Editor dispatch owner differs.')
        release(self.binding(h),self.owner(d,h))
        if not row['saved'] or not row['invocationReturned'] or row['phase']!='returned' or row['error']!='':raise CadenceError('native_write_failed','Editor returned a failure receipt; output remains unaccepted.')

    def manifest(self,d,create=False):
        path=d/'editor-wire-artifacts.json'
        if path.exists():
            row=json.loads(path.read_text(encoding='utf-8'))
            for f in row['files']:
                target=checked_path(str(d/f['relativePath']),(d,))
                if sha256(target)!=f['sha256']:raise CadenceError('target_changed','Previously verified editor proof changed.')
        else:
            if not create:raise CadenceError('invalid_native_receipt','Verified editor proof manifest is missing.')
            names=['design.dsn','editor-output.opj','native-result.json','host-after.json','entered.txt','dispatch-claim.json','payload.tcl','invoke.tcl','forwarder.json']
            write_json(path,{'files':[{'relativePath':name,'sha256':sha256(d/name)} for name in names]})
