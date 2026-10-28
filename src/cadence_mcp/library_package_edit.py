"""Package fixed fields and explicit string user properties on new OLB copies."""
import copy,json,re,shutil
from datetime import datetime,timezone
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,process_env,run_tcl
from .process_tree import run_owned_process
from .isolated_jobs import digest
from .library_vector_edit import LibraryVectorEdits
from .library_semantics import library_graph

FIXED=('referenceTemplate','footprint','pcbLibrary')
RESERVED={'value','reference','refdes','part reference','reference template','designator','pcb footprint','pcb lib','pcb library','part name','package','package name'}
def validate_package_properties(rows):
    try:
        if not isinstance(rows,list) or len(rows)>10000:raise ValueError()
        result=[];seen=set();budget=0
        for row in rows:
            if set(row)!={'packageName','referenceTemplate','footprint','pcbLibrary','designator','userPropsPermitted','userProperties'}:raise ValueError()
            if any(not isinstance(row[k],str) or len(row[k])>4096 for k in ('packageName',*FIXED,'designator')):raise ValueError()
            if row['packageName'].casefold() in seen:raise ValueError()
            seen.add(row['packageName'].casefold())
            if type(row['userPropsPermitted']) is not int or row['userPropsPermitted'] not in (0,1):raise ValueError()
            if not isinstance(row['userProperties'],list) or len(row['userProperties'])>1024:raise ValueError()
            props=[];names=set()
            for prop in row['userProperties']:
                if set(prop)!={'name','value','nativeType','editable','deletable'}:raise ValueError()
                if not isinstance(prop['name'],str) or not 1<=len(prop['name'])<=256 or not isinstance(prop['value'],str) or len(prop['value'])>16384:raise ValueError()
                if prop['name'].casefold() in names:raise ValueError()
                names.add(prop['name'].casefold())
                if type(prop['nativeType']) is not int or not 0<=prop['nativeType']<=255:raise ValueError()
                if any(type(prop[k]) is not int or prop[k] not in (0,1) for k in ('editable','deletable')):raise ValueError()
                budget+=len(prop['name'])+len(prop['value']);props.append(copy.deepcopy(prop))
            result.append({**row,'userProperties':sorted(props,key=lambda p:p['name'])})
        if budget>4*1024*1024:raise ValueError()
        return sorted(result,key=lambda r:r['packageName'])
    except (ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_package_properties','Invalid complete package property snapshot.') from error

def read_package_properties(config,source,directory):
    output=directory/(new_id('package-properties')+'.json')
    run_tcl(config,'inspect_library_package_properties.tcl',[str(source),str(output)],directory)
    if output.stat().st_size>16*1024*1024:raise CadenceError('output_limit','Package property snapshot exceeds16MiB.')
    try:return validate_package_properties(json.loads(output.read_text(encoding='utf-8')))
    except ValueError as error:raise CadenceError('invalid_worker_result','Invalid package properties JSON.') from error

def query_package_properties(library,library_id,package_id):
    with library.lock:
        session=library._session(library_id)
        matches=[p for p in session['data']['package'] if p['objectId']==package_id]
        if len(matches)!=1:raise CadenceError('object_not_found','Package does not belong to this library snapshot.')
        if 'packageProperties' not in session:
            rows=read_package_properties(library.config,session['directory']/'library.olb',session['directory'])
            if sorted(r['packageName'] for r in rows)!=sorted(p['name'] for p in session['data']['package']):raise CadenceError('target_changed','Package properties differ from the bound definitions.')
            library._session(library_id);session['packageProperties']=rows
        row=next(p for p in session['packageProperties'] if p['packageName']==matches[0]['name'])
        library._session(library_id)
        return {'libraryId':library_id,'packageId':package_id,'revision':session['revision'],'properties':copy.deepcopy(row),
                'scope':'library_package_fields_and_explicit_user_properties','readOnly':True,
                'userPropertyValueContract':{'storage':'native_string','automaticNumberOrBooleanParsing':False,'builtInDBProperties':'separate_typed_attributes'},
                'externalFootprintVerified':False,'designCacheUpdated':False}

def expected_package_edit(graph,name,changes,user_changes):
    if not isinstance(changes,dict) or set(changes)-set(FIXED) or not isinstance(user_changes,list) or len(user_changes)>64:
        raise CadenceError('invalid_package_edit','Use fixed package fields and at most64 explicit string user-property operations.')
    effective={}
    target=next((r for r in graph['packageProperties'] if r['packageName']==name),None)
    if target is None:raise CadenceError('object_not_found','Package properties are missing.')
    for key,value in changes.items():
        if value is None:continue
        if not isinstance(value,str) or len(value)>256 or any(ord(c)<32 or ord(c)==127 for c in value):raise CadenceError('invalid_package_edit','Package fields are bounded literal single-line strings.')
        if key=='referenceTemplate' and re.fullmatch(r'[A-Za-z]{1,8}\??',value) is None:raise CadenceError('invalid_package_edit','Use a bounded alphabetic reference prefix with optional question mark.')
        if value!=target[key]:effective[key]=value
    expected=copy.deepcopy(graph);new=next(r for r in expected['packageProperties'] if r['packageName']==name)
    if 'referenceTemplate' in effective:
        if target['designator']!=target['referenceTemplate']:raise CadenceError('package_designator_semantics','Distinct native package designator/template semantics require a dedicated validated operation.')
        new['designator']=effective['referenceTemplate']
        for row in expected['library']['metadata']['packages']:
            if row['packageName']==name:row['referenceTemplate']=effective['referenceTemplate']
    if 'footprint' in effective:
        for row in expected['library']['definitions']['package']:
            if row['name']==name:row['footprint']=effective['footprint']
        expected['library']['definitions']['package'].sort(key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))
    new.update(effective)
    props={r['name'].casefold():r for r in new['userProperties']};seen=set();operations=[]
    for change in user_changes:
        if not isinstance(change,dict) or set(change)!={'name','operation','value'}:raise CadenceError('invalid_package_edit','Declare explicit set/delete user-property operations.')
        key=change['name'];op=change['operation'];value=change['value']
        if not isinstance(key,str) or not 1<=len(key)<=128 or key.strip()!=key or any(ord(c)<32 or ord(c)==127 for c in key):raise CadenceError('invalid_package_edit','Invalid bounded user-property name.')
        folded=key.casefold()
        if folded in RESERVED or folded in seen:raise CadenceError('reserved_or_duplicate_property','Use fixed field setters for built-ins; each user property may appear once.')
        seen.add(folded);old=copy.deepcopy(props.get(folded))
        if old and old['name']!=key:raise CadenceError('property_case_alias','Use the exact existing user-property spelling.')
        if op=='delete':
            if value is not None or old is None:raise CadenceError('invalid_package_edit','Delete needs an existing explicit user property and no value.')
            if not old['deletable']:raise CadenceError('property_not_deletable','Native property is not deletable.')
            del props[folded]
        elif op=='set':
            if not isinstance(value,str) or len(value)>4096 or '\x00' in value:raise CadenceError('invalid_package_edit','Capture native UserProps store strings. Set requires bounded literal text; empty text differs from deletion. Typed built-in DBProps use separate operations.')
            if old and (old['nativeType']!=0 or not old['editable']):raise CadenceError('property_type_or_lock','Only editable native string user properties may be set.')
            if old and old['value']==value:continue
            if not old and not target['userPropsPermitted']:raise CadenceError('user_properties_not_permitted','Native package does not permit explicit user properties.')
            props[folded]={**old,'value':value} if old else {'name':key,'value':value,'nativeType':0,'editable':1,'deletable':1}
        else:raise CadenceError('invalid_package_edit','User operation must be set or delete.')
        operations.append({**change,'old':old})
    new['userProperties']=sorted(props.values(),key=lambda p:p['name'])
    if not effective and not operations:raise CadenceError('no_change','Requested package fields already match the snapshot.')
    return expected,effective,operations,{k:target[k] for k in (*FIXED,'designator')}

class LibraryPackageEdits(LibraryVectorEdits):
    kind='library_package'
    def _read_graph(self,source,directory):
        graph,_=super()._read_graph(source,directory)
        props=read_package_properties(self.config,source,directory)
        if sorted(p['packageName'] for p in props)!=sorted(p['name'] for p in graph['definitions']['package']):raise CadenceError('invalid_worker_result','Package property ownership differs.')
        combined={'library':graph,'packageProperties':props};path=directory/(new_id('package-graph')+'.json');write_json(path,combined)
        return combined,path
    def plan(self,library_id,package_id,changes,user_changes):
        with self.library.lock:
            session=self.library._session(library_id);data=session['data']
            package=next((p for p in data['package'] if p['objectId']==package_id),None)
            if package is None:raise CadenceError('object_not_found','Package does not belong to this library snapshot.')
            source=session['directory']/'library.olb';before,path=self._read_graph(source,session['directory'])
            if before['library']['definitions']!=library_graph(data):raise CadenceError('target_changed','Definitions differ from the bound snapshot.')
            expected,fields,operations,old=expected_package_edit(before,package['name'],changes,user_changes)
            expected_path=session['directory']/(new_id('expected-package-edit')+'.json');write_json(expected_path,expected)
            self.library._session(library_id)
            payload={'sourceLibrary':str(source),'sourceFingerprint':session['revision'],'packageId':package_id,'packageName':package['name'],
              'changes':fields,'userChanges':operations,'oldFixedFields':old,'expectedGraphDigest':digest(expected),
              'beforeEvidence':str(path),'beforeEvidenceHash':sha256(path),'expectedEvidence':str(expected_path),'expectedEvidenceHash':sha256(expected_path)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Package property plan exceeds48KB.')
            return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('packageId','packageName','changes','userChanges','oldFixedFields','sourceFingerprint')}
    def native_command(self,d,p):return [str(x) for x in [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_library_package.tcl',self.config.install_root,d/'library.olb',d/'package-edit.json',d/'native-result.json']]
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);source=checked_path(p['sourceLibrary'],(self.config.workspace_root,));target=d/'library.olb'
        with source.open('rb') as original,target.open('xb') as copied:shutil.copyfileobj(original,copied)
        if sha256(target)!=p['sourceFingerprint'] or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Package library changed during copy.')
        before=json.loads(checked_path(p['beforeEvidence'],(self.config.workspace_root,)).read_text(encoding='utf-8'))
        old=next(r for r in before['packageProperties'] if r['packageName']==p['packageName'])
        write_json(d/'package-edit.json',{'packageId':p['packageId'],'packageName':p['packageName'],'beforeProperties':old,
          'changes':p['changes'],'userChanges':[{k:r[k] for k in ('name','operation','value')} for r in p['userChanges']]})
        return run_owned_process(self.native_command(d,p),d,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def verify(self,d,p,native_completed):
        self.preflight(p);target=checked_path(str(d/'library.olb'),(d,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Package output exceeds128MiB.')
        if native_completed:
            receipt=d/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'packageId':p['packageId']}:raise CadenceError('invalid_worker_result','Package save receipt differs.')
        graph,_=self._read_graph(target,d)
        if digest(graph)!=p['expectedGraphDigest']:raise CadenceError('library_package_mismatch','Saved package fields or modeled library preservation differ from the frozen expectation.','verify')
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Package output changed during verification.')
        ident=d.name.removeprefix('plan-');artifact={'artifactId':'library-'+ident,'kind':'capture_edited_library','workspaceRelativePath':'library.olb','sha256':before,
          'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,
          'independentReopenVerified':True,'packagePropertiesVerified':True,'modeledLibraryPreservationVerified':True,'sourceModified':False,'designCacheUpdated':False,
          'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),
          'notChecked':['external_footprint','typed_user_property_edit','other_library_properties','unreferenced_native_objects','rendered_appearance','dsn_cache','instance_connectivity','native_drc']}

