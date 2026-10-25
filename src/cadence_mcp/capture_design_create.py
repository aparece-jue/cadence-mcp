"""New empty DSN from a bounded declaration, with independent root/page checks."""
from datetime import datetime,timezone
import json,re
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,run_tcl,process_env
from .isolated_jobs import digest
from .process_tree import run_owned_process

COUNT_KEYS={'part','wire','busEntry','port','global','offpage','graphic','titleblock','erc','bookmark'}
def design_name(value):
    if not isinstance(value,str) or not re.fullmatch(r'\w[\w .-]{0,63}',value) or value.strip(' .')!=value:
        raise CadenceError('invalid_document_name','Use a bounded database name without paths or control characters.')
    return value

def read_document_meta(config,design,directory):
    before=sha256(design);output=directory/(new_id('document-meta')+'.json')
    run_tcl(config,'inspect_document_meta.tcl',[str(design),str(output)],directory)
    try:
        if output.stat().st_size>8*1024*1024:raise ValueError()
        meta=json.loads(output.read_text(encoding='utf-8'))
        if set(meta)!={'rootName','schematics','pages'} or not isinstance(meta['rootName'],str):raise ValueError()
        if not isinstance(meta['schematics'],list) or not 1<=len(meta['schematics'])<=10000 or not isinstance(meta['pages'],list) or len(meta['pages'])>10000:raise ValueError()
        names=set();page_names=set()
        for s in meta['schematics']:
            if set(s)!={'name','rawRefCount'} or not isinstance(s['name'],str) or s['name'] in names or type(s['rawRefCount']) is not int or s['rawRefCount']<0:raise ValueError()
            names.add(s['name'])
        if meta['rootName'] not in names:raise ValueError()
        for p in meta['pages']:
            if set(p)!={'schematicName','name','counts'} or p['schematicName'] not in names or not isinstance(p['name'],str) or not isinstance(p['counts'],dict) or set(p['counts'])!=COUNT_KEYS:raise ValueError()
            key=(p['schematicName'],p['name'])
            if key in page_names or any(type(c) is not int or not 0<=c<=100000 for c in p['counts'].values()):raise ValueError()
            page_names.add(key)
    except (OSError,ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_worker_result','Invalid document root/page/count metadata.','decode') from error
    if sha256(design)!=before:raise CadenceError('target_changed','Design changed while reading document metadata.')
    output.unlink();return meta

def empty_definition(root_name,page_name):
    return {'schematic':[{'objectId':'s','name':root_name}],
            'page':[{'objectId':'p','schematicId':'s','name':page_name}], 'part':[], 'pin':[]}

class CaptureDesignCreates(CapturePropertyEdits):
    kind='capture_design_create'
    def plan(self,root_name,page_name):
        spec={'rootName':design_name(root_name),'pageName':design_name(page_name)}
        if any(not n.isascii() for n in spec.values()):raise CadenceError('unsupported_design_encoding','Non-ASCII new design names have not passed native save/reopen acceptance.')
        return self.create_plan({'spec':spec,'specDigest':digest(spec),'expectedDefinitionDigest':definition_baseline(empty_definition(root_name,page_name))})
    def preview(self,p):return {'operation':'create_design','spec':p['spec'],'specDigest':p['specDigest'],'sourceKind':'new_design_spec'}
    def preflight(self,p):
        spec=p['spec']
        if set(spec)!={'rootName','pageName'} or any(design_name(n)!=n for n in spec.values()) or digest(spec)!=p['specDigest'] or definition_baseline(empty_definition(spec['rootName'],spec['pageName']))!=p['expectedDefinitionDigest']:
            raise CadenceError('invalid_plan','Design declaration differs from its durable expectation.')
    def execute(self,directory,p,cancel,on_started):
        self.preflight(p)
        if (directory/'design.dsn').exists():raise CadenceError('output_exists','New design output must never overwrite or replay.')
        write_json(directory/'design-spec.json',p['spec'])
        return run_owned_process(self.native_command(directory,p),directory,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def native_command(self,directory,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'create_design.tcl',self.config.install_root,directory/'design-spec.json',directory/'design.dsn',directory/'native-result.json']
    def verify(self,directory,p,native_completed):
        self.preflight(p);target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','New design output exceeds limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'create_design'}:raise CadenceError('invalid_worker_result','New design receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['new']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('new')['sessionId']
        try:
            if definition_baseline(verifier.sessions[sid]['data'])!=p['expectedDefinitionDigest']:raise CadenceError('design_creation_mismatch','Saved design definitions differ from the declaration.','verify')
            meta=read_document_meta(self.config,target,directory)
            if meta['rootName']!=p['spec']['rootName'] or len(meta['pages'])!=1 or any(meta['pages'][0]['counts'].values()):raise CadenceError('design_creation_mismatch','Saved design root or empty page differs from declaration.','verify')
        finally:verifier.close(sid)
        if sha256(target)!=before:raise CadenceError('target_changed','New design changed during verification.')
        ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'design-'+ident,'kind':'capture_created_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['specDigest'],'sourceKind':'new_design_spec','createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'sourceKind':'new_design_spec',
                'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'declaredDefinitionsVerified':True,'rootAndPageCountsVerified':True,
                'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['opj_project_creation','custom_plugin_objects','page_format_rendering','native_drc','schematic_delete_dependencies']}
