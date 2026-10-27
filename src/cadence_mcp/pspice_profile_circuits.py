"""Fixed native profile-to-CIR tasks consuming verified Capture NET/ALS artifacts."""
import json,os,re,uuid
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from .core import CadenceError,checked_path,sha256,write_json
from .isolated_jobs import IsolatedJobs
from .pspice_input import PSpiceInputs,REFERENCE,ARGUMENT
from .pspice_profile_configuration import inspect_global_selection
from .environment import ADAPTERS,process_env
from .gui_loader import tcl_string
from .process_tree import run_owned_process

class PSpiceProfileCircuits(IsolatedJobs):
    kind='pspice_profile_circuit'

    def __init__(self,config,netlists,inputs):
        super().__init__(config);self.netlists=netlists;self.inputs=inputs

    def _json(self,path):
        path=checked_path(str(path),(self.config.workspace_root,))
        if path.stat().st_size>1048576:raise CadenceError('input_limit','Profile task JSON exceeds one MiB.')
        try:return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError) as error:raise CadenceError('invalid_profile_task','Incomplete profile task JSON.') from error

    def _net(self,ident,digest):
        d,_,row=self.netlists._load(ident)
        if row['digest']!=digest:raise CadenceError('plan_digest_mismatch','NET/ALS plan digest differs.')
        if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified NET/ALS artifacts can generate a circuit.')
        result=self.netlists._verified_result(d,row)
        return d,row,result

    def plan(self,netlist_plan_id,netlist_plan_digest,libraries,include_aliases,expected_directives,input_budget='standard',configuration_ini=None):
        if type(include_aliases) is not bool or not isinstance(libraries,list) or len(libraries)>16:
            raise CadenceError('invalid_profile_configuration','Select explicit libraries and alias inclusion.')
        if not isinstance(expected_directives,list) or not 1<=len(expected_directives)<=16 or any(not isinstance(x,str) or len(x)>4096 or '\n' in x or '\r' in x or '\x00' in x or not re.match(r'^\.(?:OP|DC|AC|TRAN|OPTIONS|PROBE64|PROBE)(?:\s|$)',x,re.I) for x in expected_directives):
            raise CadenceError('invalid_profile_configuration','Declare bounded expected analysis/probe/option directives.')
        if not any(re.match(r'^\.(?:OP|DC|AC|TRAN)(?:\s|$)',x,re.I) for x in expected_directives):
            raise CadenceError('invalid_profile_configuration','At least one independent analysis directive is required.')
        netdir,row,result=self._net(netlist_plan_id,netlist_plan_digest)
        origin=None
        if configuration_ini is not None:
            if libraries:raise CadenceError('invalid_profile_configuration','Choose explicit libraries or one inherited INI, never both.')
            origin=inspect_global_selection(self.config,netdir,row['plan']['payload']['snapshot']['description'],configuration_ini)
            libraries=origin['selectedLibraries']
        selected=[]
        for value in libraries:
            path=checked_path(value,self.config.read_roots)
            if any(c in str(path) for c in ('"','\r','\n','\x00')):raise CadenceError('unsupported_reference','Library filename cannot be represented literally.')
            if path in selected:raise CadenceError('invalid_profile_configuration','Duplicate explicit library.')
            selected.append(path)
        configdir=self.config.workspace_root/('profile-config-'+uuid.uuid4().hex);configdir.mkdir()
        synthetic=configdir/'models.cir'
        synthetic.write_text('* Explicit profile library closure; never solved\n'+''.join('.LIB "'+x.as_posix()+'"\n' for x in selected)+'.OP\n.END\n',encoding='utf-8')
        resolver=PSpiceInputs(replace(self.config,read_roots=self.config.read_roots+(configdir,)))
        prepared=resolver.prepare(str(synthetic),input_encoding='preserve-bytes',input_budget=input_budget)
        models=resolver.inputs[prepared['simulationId']];manifest=models['manifest']
        p={'netlistPlanId':netlist_plan_id,'netlistPlanDigest':netlist_plan_digest,'netlistManifestSha256':result['artifact']['sha256'],
           'description':row['plan']['payload']['snapshot']['description'],'sourceDesignRevision':result['sourceDesignRevision'],
           'configurationMode':'explicit_libraries','includeAliases':include_aliases,'expectedDirectives':expected_directives,'inputBudget':input_budget,
           'models':{'directory':str(models['directory']),'manifestSha256':models['manifestHash'],'configDirectory':str(configdir),
                     'libraries':[next(f['relativePath'] for f in manifest['files'] if f['sourcePath']==str(x)) for x in selected]},
           'adapterHashes':{name:sha256(ADAPTERS/name) for name in ('json.tcl','profile_circuit_job.tcl')}}
        if origin is not None:
            p['configurationMode']='inherited_global_library_selection'
            p['configurationOrigin']=origin
            p['adapterHashes']['profile_configuration_query.tcl']=sha256(ADAPTERS/'profile_configuration_query.tcl')
        if len(json.dumps(p,ensure_ascii=False).encode('utf-8'))>49152:raise CadenceError('plan_limit','Profile configuration exceeds its durable plan record budget.')
        self.preflight(p);return self.create_plan(p)

    def preview(self,p):
        return {'sourceDesignRevision':p['sourceDesignRevision'],'netlistPlanId':p['netlistPlanId'],'profileName':p['description']['profileName'],
                'configurationMode':p['configurationMode'],'inputBudget':p.get('inputBudget','standard'),'explicitLibraryCount':len(p['models']['libraries']),
                'includeAliases':p['includeAliases'],'expectedDirectives':p['expectedDirectives'],'sourceWillBeModified':False,
                'solverRun':False,'globalIniWillBeModified':False,'scope':p['description']['scope']}

    def _models(self,p,check_sources=False):
        root=checked_path(p['models']['directory'],(self.config.workspace_root,));target=root/'input-manifest.json'
        if sha256(target)!=p['models']['manifestSha256']:raise CadenceError('target_changed','Frozen library closure manifest changed.')
        manifest=self._json(target);configdir=checked_path(p['models']['configDirectory'],(self.config.workspace_root,))
        for f in manifest['files']:
            for key,hashkey in (('relativePath','preparedSha256'),('originalRelativePath','sourceSha256')):
                if sha256(checked_path(str(root/f[key]),(root,)))!=f[hashkey]:raise CadenceError('target_changed','Frozen library closure changed.')
            if check_sources:
                source=checked_path(f['sourcePath'],self.config.read_roots+(configdir,))
                if sha256(source)!=f['sourceSha256']:raise CadenceError('source_changed','Explicit model source changed after planning.')
        return root,manifest

    def preflight(self,p):
        _,_,net=self._net(p['netlistPlanId'],p['netlistPlanDigest'])
        if net['artifact']['sha256']!=p['netlistManifestSha256']:raise CadenceError('target_changed','Source NET/ALS artifact changed.')
        names=['json.tcl','profile_circuit_job.tcl']
        if 'configurationOrigin' in p:
            names.append('profile_configuration_query.tcl');origin=p['configurationOrigin']
            source=checked_path(origin['sourceIni'],self.config.read_roots)
            root=checked_path(origin['snapshotDirectory'],(self.config.workspace_root,))
            if (sha256(source)!=origin['sourceIniSha256'] or sha256(root/'selected.ini')!=origin['selectedIniSha256']
                or sha256(root/'native-result.json')!=origin['nativeResultSha256'] or sha256(root/'configuration-proof.json')!=origin['proofSha256']):
                raise CadenceError('source_changed','Frozen native-checked INI selection changed.')
        if p['adapterHashes']!={name:sha256(ADAPTERS/name) for name in names}:
            raise CadenceError('target_changed','Fixed profile adapter changed.')
        self._models(p,True)

    def _model_bytes(self,modelsroot,f,modeldir):
        raw=(modelsroot/f['originalRelativePath']).read_bytes();text=raw.decode('utf-8-sig',errors='surrogateescape');lines=text.splitlines(keepends=True)
        for ref in f['references']:
            old=lines[ref['line']-1];ending='\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else '\r' if old.endswith('\r') else ''
            target=checked_path(str(modeldir/ref['targetRelativePath']),(modeldir,),exists=False)
            lines[ref['line']-1]='.'+ref['directive']+' "'+target.as_posix()+'"'+ending
        return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+''.join(lines).encode('utf-8',errors='surrogateescape')

    def _stage(self,d,p):
        netdir,_,_=self._net(p['netlistPlanId'],p['netlistPlanDigest']);desc=p['description'];files=[]
        original=self._json(netdir/'netlist-artifacts.json');hashes={f['relativePath']:f['sha256'] for f in original['files']}
        roles=[desc[x+'Target'] for x in ('project','design','profile')]+[desc['netlistTarget'],desc['aliasesTarget']]
        for relative in roles:
            source=checked_path(str(netdir/'project'/relative),(netdir,));target=checked_path(str(d/'project'/relative),(d,),exists=False)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(source.read_bytes())
            if sha256(target)!=hashes['project/'+relative] or sha256(source)!=hashes['project/'+relative]:raise CadenceError('target_changed','Staged profile input differs from accepted NET/ALS job.')
            files.append({'relativePath':target.relative_to(d).as_posix(),'sha256':sha256(target)})
        modelsroot,manifest=self._models(p,True);modeldir=d/'project/models'
        for f in manifest['files'][1:]:
            target=checked_path(str(modeldir/f['relativePath']),(d,),exists=False);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(self._model_bytes(modelsroot,f,modeldir))
            files.append({'relativePath':target.relative_to(d).as_posix(),'sha256':sha256(target)})
        circuit=d/'project'/desc['circuitTarget'];circuit.parent.mkdir(parents=True,exist_ok=True)
        lines=[]
        for relative in p['models']['libraries']:
            lines.append('.LIB "'+os.path.relpath(modeldir/relative,circuit.parent)+'"')
        if p['includeAliases']:lines.append('.INC "'+os.path.relpath(d/'project'/desc['aliasesTarget'],circuit.parent)+'"')
        ini=d/'private.ini';ini.write_text('[PSPICE NETLIST]\n'+''.join('LINE'+str(i+1)+'='+line+'\n' for i,line in enumerate(lines)),encoding='utf-8')
        files.append({'relativePath':'private.ini','sha256':sha256(ini)})
        if 'configurationOrigin' in p:
            origin=p['configurationOrigin'];source=checked_path(origin['snapshotDirectory'],(self.config.workspace_root,))
            target_root=d/'configuration-origin';target_root.mkdir()
            for name,key in [('selected.ini','selectedIniSha256'),('native-result.json','nativeResultSha256'),('configuration-proof.json','proofSha256')]:
                target=target_root/name
                with target.open('xb') as stream:stream.write((source/name).read_bytes())
                if sha256(target)!=origin[key] or sha256(source/name)!=origin[key]:raise CadenceError('target_changed','Inherited configuration provenance changed while staging.')
                files.append({'relativePath':target.relative_to(d).as_posix(),'sha256':sha256(target)})
        write_json(d/'staged-inputs.json',{'files':files,'configurationDirectives':lines})
        return circuit

    def execute(self,d,p,cancel,on_started):
        self.preflight(p)
        if {x.name for x in d.iterdir()}!={'plan.json'}:raise CadenceError('preexisting_profile_output','Profile task directory contains preexisting output.')
        circuit=self._stage(d,p);desc=p['description'];nonce=d.name.removeprefix('plan-')
        args=[self.config.install_root,d/'project'/desc['projectTarget'],d/'project'/desc['profileTarget'],d/'private.ini',circuit,d/'native-result.json',nonce]
        code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'profile_circuit_job.tcl').as_posix())+'\n'
        code+='::cmcpProfileCircuit::run '+' '.join(tcl_string(x.as_posix() if isinstance(x,Path) else x) for x in args)+'\n'
        script=d/'generate.tcl';script.write_text(code,encoding='utf-8')
        process=run_owned_process([self.config.install_root/'tcltk/bin/tclsh.exe',script],d,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
        write_json(d/'worker-process.json',process);return process

    def verify(self,d,p,native_completed):
        receipt=self._json(d/'native-result.json');process=self._json(d/'worker-process.json');nonce=d.name.removeprefix('plan-');circuit=checked_path(str(d/'project'/p['description']['circuitTarget']),(d,))
        if (receipt.get('jobId')!=nonce or receipt.get('pid')!=process.get('pid') or receipt.get('invocationReturned') is not True
            or receipt.get('phase')!='returned' or any(receipt.get(k)!='0' for k in ('loadResult','libincResult','updateResult'))
            or receipt.get('error')!='' or Path(receipt.get('cirPath','')).resolve()!=circuit
            or process.get('state')!='exited' or process.get('returnCode')!=0 or process.get('remainingOwnedProcesses')!=0
            or process.get('rootExitSignalConfirmed') is not True or process.get('observedProcessExitSignalsConfirmed') is not True):
            raise CadenceError('native_profile_failed','Profile native completion/identity/return receipt is invalid.','verify')
        self._net(p['netlistPlanId'],p['netlistPlanDigest'])
        modelsroot,models=self._models(p)
        for f in models['files'][1:]:
            if (d/'project/models'/f['relativePath']).read_bytes()!=self._model_bytes(modelsroot,f,d/'project/models'):
                raise CadenceError('target_changed','Staged model reference relocation differs from its frozen original.')
        staged=self._json(d/'staged-inputs.json')
        for f in staged['files']:
            if sha256(checked_path(str(d/f['relativePath']),(d,)))!=f['sha256']:raise CadenceError('target_changed','Staged profile input changed.')
        if not 0<circuit.stat().st_size<=8*1024*1024:raise CadenceError('input_limit','Generated CIR is empty or oversized.')
        text=circuit.read_text(encoding='utf-8-sig');actual=[line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('*')]
        for expected in p['expectedDirectives']:
            if actual.count(expected)!=1:raise CadenceError('profile_directive_mismatch','Generated CIR differs from an independently declared directive.','verify')
        found=[]
        for line in actual:
            match=REFERENCE.match(line)
            if not match:continue
            value=ARGUMENT.fullmatch(match.group(2))
            if not value:raise CadenceError('unsupported_reference','Native folded/dynamic reference is not accepted.','verify')
            name=next(x for x in value.groups() if x is not None)
            found.append((match.group(1).upper(),checked_path(str(circuit.parent/name),(d,))))
        expected=[('LIB',d/'project/models'/x) for x in p['models']['libraries']]
        if p['includeAliases']:expected.append(('INC',d/'project'/p['description']['aliasesTarget']))
        expected.append(('INC',d/'project'/p['description']['netlistTarget']))
        if found!=[(kind,path.resolve()) for kind,path in expected]:raise CadenceError('profile_reference_mismatch','Native CIR references differ from explicit configuration and accepted NET/ALS.','verify')
        files=staged['files']+[{'relativePath':x,'sha256':sha256(d/x)} for x in ('staged-inputs.json','generate.tcl','native-result.json','worker-process.json')]
        files.append({'relativePath':circuit.relative_to(d).as_posix(),'sha256':sha256(circuit)})
        manifest={'kind':self.kind,'sourceDesignRevision':p['sourceDesignRevision'],'netlistManifestSha256':p['netlistManifestSha256'],
                  'configurationMode':p['configurationMode'],'expectedDirectives':p['expectedDirectives'],'files':files,'solverRun':False}
        if 'configurationOrigin' in p:
            origin=p['configurationOrigin']
            manifest['configurationOrigin']={key:origin[key] for key in ('sourceIniSha256','proofSha256','scope')}
        target=d/'circuit-artifacts.json'
        if target.exists():
            if self._json(target)!=manifest:raise CadenceError('target_changed','Profile task artifact manifest changed.')
        else:write_json(target,manifest)
        created=self._json(d/'plan.json')['plan']['createdAt']
        artifact={'artifactId':'profile-circuit-'+nonce,'kind':self.kind,'workspaceRelativePath':'circuit-artifacts.json','sha256':sha256(target),'size':target.stat().st_size,
                  'producedByJob':nonce,'sourceFingerprint':p['sourceDesignRevision'],'sourceKind':'file_fingerprint','createdAt':datetime.fromtimestamp(created,timezone.utc).isoformat(),'validationState':'validated'}
        return {'outputWorkspaceRelativePath':str(d.relative_to(self.config.workspace_root)),'artifact':artifact,'circuitRelativePath':circuit.relative_to(d).as_posix(),
                'nativeCompletionVerified':True,'explicitConfigurationVerified':True,'configurationMode':p['configurationMode'],'nativeCheckedIniSelection':('configurationOrigin' in p),'declaredDirectivesVerified':True,'sourceDesignRevision':p['sourceDesignRevision'],
                'sourceModified':False,'globalIniModified':False,'solverRun':False,'notChecked':['inherited_nominal_configuration','complete_profile_semantics','solver','numerical_results']}

    def _verified_result(self,d,row):
        result=super()._verified_result(d,row);manifest=self._json(d/'circuit-artifacts.json')
        for f in manifest['files']:
            if sha256(checked_path(str(d/f['relativePath']),(d,)))!=f['sha256']:raise CadenceError('target_changed','Verified profile artifact changed.')
        return result

    def open_input(self,plan_id,plan_digest):
        d,_,row=self._load(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Profile task digest differs.')
        if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified profile CIR can prepare solver inputs.')
        result=self._verified_result(d,row)
        resolver=PSpiceInputs(replace(self.config,read_roots=(d,)))
        opened=resolver.prepare(str(d/result['circuitRelativePath']),input_encoding='preserve-bytes',input_budget=row['plan']['payload'].get('inputBudget','standard'))
        with self.inputs.lock:
            if len(self.inputs.inputs)>=64:raise CadenceError('input_limit','Too many prepared solver inputs.')
            self.inputs.inputs[opened['simulationId']]=resolver.inputs.pop(opened['simulationId'])
        return {**opened,'producedByProfilePlan':plan_id,'profileManifestSha256':result['artifact']['sha256'],'sourceDesignRevision':result['sourceDesignRevision']}
