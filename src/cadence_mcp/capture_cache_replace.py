"""Durable source-qualified compatible-package replacement on new DSN copies."""
import copy,json,shutil
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_cache_bindings import query_cache_binding
from .capture_references import read_units
from .capture_place import validate_pins
from .capture_wire import inventory,connection_digest,point
from .library_semantics import library_graph
from .core import CadenceError,checked_path,new_id,sha256,write_json
from .environment import ADAPTERS,run_tcl,process_env
from .isolated_jobs import digest
from .process_tree import run_owned_process

NEW_LIBRARY='__NEW_OWNED_LIBRARY__'
BINDING_FIELDS={'Source Library','Source Package','Source Part','Graphic'}

def subset(data,package_id):
    return {k:[r for r in rows if (r['objectId'] if k=='package' else r['packageId'])==package_id] for k,rows in data.items()}

def cache_groups(snapshot):
    origins={r['cachePackageId']:r for r in snapshot['origins']};rows=[]
    for package in snapshot['definitions']['package']:
        o=origins[package['objectId']]
        rows.append({'isCached':o['isCached'],'sourceLibrary':o['sourceLibrary'].casefold(),'packageName':package['name'],'graph':library_graph(subset(snapshot['definitions'],package['objectId']))})
    return sorted(rows,key=lambda r:json.dumps(r,ensure_ascii=False,sort_keys=True))

def normalize_state(rows,units):
    try:
        if not isinstance(rows,list) or len(rows)!=len(units) or len(rows)>128:raise ValueError('instance coverage')
        result=[];seen=set();text_bytes=0
        for row in rows:
            if set(row)!={'nativeId','partId','schematicName','pageName','reference','geometry','effective','user','display'}:raise ValueError('shape')
            u=units.get(row['partId'])
            if u is None or type(row['nativeId']) is not int or row['nativeId']!=u['nativeId'] or row['nativeId'] in seen:raise ValueError('native identity')
            if any(row[k]!=u[k] for k in ('schematicName','pageName','reference')):raise ValueError('scope')
            seen.add(row['nativeId']);g=row['geometry']
            if set(g)!={'physicalPinNumbersApplicable','location','rotationCode','mirrorCode','pins'} or type(g['physicalPinNumbersApplicable']) is not bool or g['physicalPinNumbersApplicable']!=(u['kind']=='placed') or not point(g['location']) or any(type(g[k]) is not int for k in ('rotationCode','mirrorCode')) or not isinstance(g['pins'],list) or len(g['pins'])>500:raise ValueError('geometry')
            for pin in g['pins']:
                if set(pin)!={'numberState','number','name','hotSpot'} or type(pin['numberState']) is not int or (pin['numberState']!=0 and not (u['kind']=='drawn' and pin['numberState']==1021 and pin['number']=='')) or not point(pin['hotSpot']) or any(not isinstance(pin[k],str) or len(pin[k])>512 for k in ('number','name')):raise ValueError('pin')
            out={k:copy.deepcopy(row[k]) for k in ('nativeId','schematicName','pageName','reference','geometry')};out['geometry']['pins'].sort(key=lambda p:(p['number'],p['name']))
            for layer in ('effective','user','display'):
                props=row[layer];names=set()
                if not isinstance(props,list) or len(props)>512:raise ValueError('property count')
                for prop in props:
                    fields={'name','value'}|({'nativeType','editable','deletable'} if layer=='user' else {'location','rotationCode','displayTypeCode','colorCode'} if layer=='display' else set())
                    if set(prop)!=fields or any(not isinstance(prop[k],str) for k in ('name','value')) or not 1<=len(prop['name'])<=256 or len(prop['value'])>16384 or prop['name'] in names:raise ValueError('property')
                    names.add(prop['name']);text_bytes+=len(prop['name'].encode('utf-8'))+len(prop['value'].encode('utf-8'))
                    if layer=='user' and (type(prop['nativeType']) is not int or not 0<=prop['nativeType']<=255 or any(type(prop[k]) is not int or prop[k] not in (0,1) for k in ('editable','deletable'))):raise ValueError('user type')
                    if layer=='display' and (not point(prop['location']) or any(type(prop[k]) is not int for k in ('rotationCode','displayTypeCode','colorCode'))):raise ValueError('display')
                out[layer]=sorted(copy.deepcopy(props),key=lambda p:p['name'])
            result.append(out)
        if seen!={u['nativeId'] for u in units.values()} or text_bytes>8*1024*1024:raise ValueError('coverage/budget')
        return sorted(result,key=lambda r:r['nativeId'])
    except (ValueError,TypeError,KeyError,AttributeError) as error:raise CadenceError('invalid_cache_instance_state','Complete modeled geometry/property layers must match independent native instance identities.') from error

def read_state(config,design,directory,units):
    output=directory/(new_id('cache-instance-state')+'.json')
    run_tcl(config,'inspect_cache_replace_state.tcl',[str(design),str(output),'100000','512'],directory)
    if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Instance state exceeds32MiB.')
    result=normalize_state(json.loads(output.read_text(encoding='utf-8')),units);output.unlink();return result

def expected_replacement(data,units,qualified,old_binding,library,package_id,declarations,state):
    package=next((p for p in library['package'] if p['objectId']==package_id),None)
    if package is None:raise CadenceError('object_not_found','Replacement package is outside the library snapshot.')
    affected=[b for b in qualified['bindings'] if b['cachePackageId']==old_binding['cachePackageId']]
    if not 1<=len(affected)<=64 or any(not all(b[k] for k in ('isCached','lookupMatchesPlaced','originVerified')) for b in affected):raise CadenceError('unsupported_cache_group','A complete verified affected group of1..64 instances is required.')
    if not isinstance(declarations,list) or len(declarations)!=len(affected) or any(not isinstance(d,dict) or set(d)!={'partId','libraryPartId','pins'} for d in declarations) or len({d['partId'] for d in declarations})!=len(declarations):raise CadenceError('incomplete_cache_expectations','Declare each affected instance, source part and every expected pin exactly once.')
    by_id={d['partId']:d for d in declarations}
    if set(by_id)!={b['partId'] for b in affected}:raise CadenceError('incomplete_cache_expectations','Declarations must exactly cover the source-qualified cache group.')
    expected_data=copy.deepcopy(data);expected_state=copy.deepcopy(state);expected_units=copy.deepcopy(units);changes=[]
    for b in affected:
        u=units[b['partId']];d=by_id[b['partId']]
        if u['isExternalDesignPart'] or u['packageSize']!=package['size']:raise CadenceError('package_structure_change','External designs and package-size changes require a separate verified mapping operation.')
        part=next((p for p in library['part'] if p['objectId']==d['libraryPartId'] and p['packageId']==package_id),None)
        if part is None:raise CadenceError('object_not_found','Replacement view is not in the selected package.')
        device=next(v for v in library['device'] if v['objectId']==part['deviceId'])
        if device['designator']!=u['deviceDesignator']:raise CadenceError('device_mapping_mismatch','Compatible replacement preserves device designators.')
        source_pins=[p for p in library['pin'] if p['partId']==part['objectId']];validate_pins(source_pins,d['pins'])
        old_pins=[p for p in data['pin'] if p['partId']==b['partId']]
        if len(old_pins)!=len(d['pins']) or len({p['number'] for p in d['pins']})!=len(d['pins']) or len({p['number'] for p in old_pins})!=len(old_pins) or {p['number'] for p in old_pins}!={p['number'] for p in d['pins']}:raise CadenceError('physical_pin_mapping_change','Compatible replacement requires the same unambiguous physical pad numbers.')
        old_by_number={p['number']:p for p in old_pins}
        old_geometry=next(r['geometry'] for r in state if r['nativeId']==u['nativeId'])
        old_hotspots={p['number']:p['hotSpot'] for p in old_geometry['pins']}
        if any(pin['hotSpot']!=old_hotspots.get(pin['number']) for pin in d['pins']):raise CadenceError('cache_hotspot_change','Compatible replacement preserves terminal hotspots; moving attached terminals requires a separately verified rewiring operation.')
        for pin in d['pins']:
            old=old_by_number[pin['number']]
            if (pin['connected'],pin['net'] or '')!=(old['connected'],old['net']):raise CadenceError('cache_connectivity_change','Compatible cache replacement cannot silently reconnect a physical pin.')
            row=next(p for p in expected_data['pin'] if p['partId']==b['partId'] and p['number']==pin['number']);row['name']=pin['name']
        row=next(r for r in expected_state if r['nativeId']==u['nativeId'])
        if any(p['nativeType']!=0 or p['name'] in BINDING_FIELDS for p in row['user']):raise CadenceError('unsupported_override_type','Typed or source-binding user overrides require separately verified preservation.')
        values={p['name']:p['value'] for p in row['effective']}
        if not {'Value','PCB Footprint',*BINDING_FIELDS}<=set(values):raise CadenceError('property_unavailable','Required effective values and binding fields are missing.')
        fields={'Source Library':NEW_LIBRARY,'Source Package':package['name'],'Source Part':part['name'],'Graphic':part['name']}
        for prop in row['effective']:
            if prop['name'] in fields:prop['value']=fields[prop['name']]
        row['geometry']['pins']=sorted([{**{k:copy.deepcopy(p[k]) for k in ('number','name','hotSpot')},'numberState':0} for p in d['pins']],key=lambda p:(p['number'],p['name']))
        expected_units[b['partId']].update(packageName=package['name'],sourceLib=NEW_LIBRARY,sourcePart=part['name'])
        changes.append({'partId':b['partId'],'nativeId':u['nativeId'],'reference':u['reference'],'schematicName':u['schematicName'],'pageName':u['pageName'],'deviceDesignator':u['deviceDesignator'],'oldSourcePart':u['sourcePart'],'partName':part['name'],'pins':copy.deepcopy(d['pins']),'preserveProperties':{k:values[k] for k in ('Value','PCB Footprint')},'userProperties':copy.deepcopy(row['user'])})
    return package,changes,expected_data,expected_state,expected_units

def unit_graph(units):
    return sorted([{k:v for k,v in row.items() if k!='partId'} for row in units.values()],key=lambda r:r['nativeId'])

class CaptureCacheReplacements(CapturePropertyEdits):
    kind='capture_cache_replace';max_record_bytes=512*1024
    def __init__(self,config,capture,library):super().__init__(config,capture);self.library=library
    def plan(self,sid,part_id,library_id,package_id,expectations):
        with self.capture.lock,self.library.lock:
            session=self.capture._session(sid);lib=self.library._session(library_id)
            bound=query_cache_binding(self.capture,sid,part_id);qualified=session['qualifiedCache'];units=read_units(self.capture,sid)
            state=read_state(self.config,session['design'],session['design'].parent,units)
            package,changes,expected_data,expected_state,expected_units=expected_replacement(session['data'],units,qualified,bound['binding'],lib['data'],package_id,expectations,state)
            before_groups=cache_groups(qualified);old=bound['binding'];new_groups=copy.deepcopy(before_groups)
            matches=[g for g in new_groups if g['isCached'] and g['sourceLibrary']==old['sourceLibrary'].casefold() and g['packageName']==old['sourcePackage']]
            if len(matches)!=1:raise CadenceError('ambiguous_cache_source','Source-qualified cache group is not unique.')
            new_groups.remove(matches[0]);source_graph=library_graph(subset(lib['data'],package_id))
            new_groups.append({'isCached':True,'sourceLibrary':NEW_LIBRARY,'packageName':package['name'],'graph':source_graph})
            evidence={'state':expected_state,'units':unit_graph(expected_units),'cacheGroups':sorted(new_groups,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))}
            path=session['design'].parent/(new_id('expected-cache-replace')+'.json');write_json(path,evidence)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'sourceLibrary':str(lib['directory']/'library.olb'),'libraryFingerprint':lib['revision'],
                     'oldSourceLibrary':old['sourceLibrary'],'oldPackageName':old['sourcePackage'],'newPackageName':package['name'],'changes':changes,'expectedEvidence':str(path),'expectedEvidenceHash':sha256(path),
                     'expectedDefinitionDigest':definition_baseline(expected_data),'expectedConnectionDigest':connection_digest(session['data'],inventory(self.capture,sid))}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>128*1024:raise CadenceError('plan_limit','Cache replacement plan exceeds128KiB.')
            self.capture._session(sid);self.library._session(library_id);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('oldSourceLibrary','oldPackageName','newPackageName','changes','sourceFingerprint','libraryFingerprint')}
    def preflight(self,p):
        for name,key in [('sourceDesign','sourceFingerprint'),('sourceLibrary','libraryFingerprint'),('expectedEvidence','expectedEvidenceHash')]:
            path=checked_path(p[name],(self.config.workspace_root,))
            if sha256(path)!=p[key]:raise CadenceError('target_changed','A frozen cache replacement input or expectation changed.')
    def execute(self,d,p,cancel,on_started):
        self.preflight(p)
        for key,name,fp in [('sourceDesign','design.dsn','sourceFingerprint'),('sourceLibrary','library.olb','libraryFingerprint')]:
            source=checked_path(p[key],(self.config.workspace_root,))
            with source.open('rb') as original,(d/name).open('xb') as out:shutil.copyfileobj(original,out)
            if sha256(d/name)!=p[fp] or sha256(source)!=p[fp]:raise CadenceError('target_changed','Frozen input changed during isolated copy.')
        request={'oldName':p['oldPackageName'],'oldLib':p['oldSourceLibrary'],'newName':p['newPackageName'],'newLib':str(d/'library.olb'),'changes':p['changes']};write_json(d/'cache-replace.json',request)
        return run_owned_process([self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'replace_cache.tcl',self.config.install_root,d/'design.dsn',d/'cache-replace.json',d/'native-result.json'],d,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def _verified_result(self,d,row):
        p=row['plan']['payload']
        if sha256(checked_path(str(d/'library.olb'),(d,)))!=p['libraryFingerprint']:raise CadenceError('target_changed','Verified replacement library copy changed.')
        return super()._verified_result(d,row)
    def verify(self,d,p,native_completed):
        self.preflight(p);target=checked_path(str(d/'design.dsn'),(d,));before=sha256(target);library=checked_path(str(d/'library.olb'),(d,))
        if sha256(library)!=p['libraryFingerprint']:raise CadenceError('target_changed','Private replacement library changed.')
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Replacement output exceeds128MiB.')
        if native_completed:
            f=d/'native-result.json'
            if f.stat().st_size>4096 or json.loads(f.read_text(encoding='utf-8'))!={'saved':True,'changed':len(p['changes'])}:raise CadenceError('invalid_worker_result','Replacement receipt differs.')
        expected=json.loads(checked_path(p['expectedEvidence'],(self.config.workspace_root,)).read_text(encoding='utf-8'))
        cap=CaptureService(self.config);cap.workspaces['output']={'directory':d,'manifest':{'copiedFingerprint':before}};sid=cap.open('output')['sessionId']
        try:
            data=cap.sessions[sid]['data'];units=read_units(cap,sid)
            if definition_baseline(data)!=p['expectedDefinitionDigest'] or connection_digest(data,inventory(cap,sid))!=p['expectedConnectionDigest']:raise CadenceError('cache_connectivity_mismatch','Reopened definitions or connection objects differ from preservation expectations.','verify')
            changes={r['nativeId']:r for r in p['changes']};selected=[u for u in units.values() if u['nativeId'] in changes]
            if len(selected)!=len(changes):raise CadenceError('cache_identity_mismatch','Replaced instances lost stable native identity.')
            for u in selected:query_cache_binding(cap,sid,u['partId'])
            qualified=cap.sessions[sid]['qualifiedCache'];actual_groups=cache_groups(qualified)
            for g in actual_groups:
                if g['isCached'] and g['sourceLibrary']==str(library).casefold() and g['packageName']==p['newPackageName']:g['sourceLibrary']=NEW_LIBRARY
            if sorted(actual_groups,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))!=expected['cacheGroups']:raise CadenceError('cache_definition_mismatch','Source-qualified new or unrelated cache definitions differ.','verify')
            actual_state=read_state(self.config,target,d,units)
            for row in actual_state:
                if row['nativeId'] in changes:
                    prop=next((v for v in row['effective'] if v['name']=='Source Library'),None)
                    if prop is None or prop['value'].casefold()!=str(library).casefold():raise CadenceError('cache_source_mismatch','Replacement instance source library differs.')
                    prop['value']=NEW_LIBRARY
            if actual_state!=expected['state']:raise CadenceError('cache_instance_state_mismatch','An instance lost declared geometry, effective/user properties or modeled display layout.','verify')
            for u in units.values():
                if u['nativeId'] in changes:
                    if u['sourceLib'].casefold()!=str(library).casefold():raise CadenceError('cache_source_mismatch','Native source key differs.')
                    u['sourceLib']=NEW_LIBRARY
            if unit_graph(units)!=expected['units']:raise CadenceError('cache_identity_mismatch','A replaced or unrelated instance identity differs.','verify')
            for change in p['changes']:
                out=d/(new_id('cache-view')+'.json')
                run_tcl(self.config,'inspect_placed_view.tcl',[str(target),str(library),str(out),change['schematicName'],change['pageName'],change['reference'],p['newPackageName'],change['deviceDesignator'],change['partName']],d)
                if json.loads(out.read_text(encoding='utf-8')).get('matches') is not True:raise CadenceError('cache_view_mismatch','Placed source view differs from the frozen replacement library.','verify')
        finally:cap.close(sid)
        self.preflight(p)
        if sha256(target)!=before or sha256(library)!=p['libraryFingerprint']:raise CadenceError('target_changed','Replacement output/input changed during verification.')
        ident=d.name.removeprefix('plan-');artifact={'artifactId':'cache-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'sourceQualifiedCacheGraphVerified':True,'modeledAllInstanceStateVerified':True,'sourceViewsVerified':True,'changedInstanceCount':len(p['changes']),'sourceModified':False,'libraryModified':False,'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['full_inheritance_origin','display_font_and_render','unrelated_cache_vector_graphics','occurrence_connectivity','external_model_or_footprint','native_drc','electrical_behavior']}

