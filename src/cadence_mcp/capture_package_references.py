"""Definition-level whole-package reference maps with unchanged unit ownership and cache state."""
import copy,json
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_references import REF,read_units
from .capture_edit import definition_baseline
from .capture_cache_bindings import query_cache_binding
from .capture_cache_replace import read_state,cache_groups,unit_graph
from .capture_wire import inventory,connection_digest
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .isolated_jobs import digest

REFERENCE_FIELDS={'Reference','Part Reference'}

def package_reference_map(data,units,bindings,mappings):
    if not isinstance(mappings,list) or not 1<=len(mappings)<=64:raise CadenceError('invalid_reference_map','Declare1..64 package representative mappings.')
    parts={r['objectId']:r for r in data['part']};by_binding={r['partId']:r for r in bindings};selected={};groups=[];group_keys=set();destinations=set()
    for mapping in mappings:
        if not isinstance(mapping,dict) or set(mapping)!={'partId','newReference'} or not isinstance(mapping['partId'],str) or not isinstance(mapping['newReference'],str):raise CadenceError('invalid_reference_map','Invalid package mapping shape.')
        owner=units.get(mapping['partId']);new=mapping['newReference']
        if owner is None:raise CadenceError('object_not_found','Representative is outside this design session.')
        if owner['kind']!='placed' or owner['isExternalDesignPart'] or not 1<=owner['packageSize']<=16:raise CadenceError('unsupported_reference_scope','Choose an internal placed package with1..16 device positions.')
        old=owner['reference'];before=REF.fullmatch(old);after=REF.fullmatch(new)
        if not before or not after or len(new)>64 or before[1].casefold()!=after[1].casefold():raise CadenceError('invalid_reference','Use an explicit numbered base reference with the current prefix.')
        if old==new:raise CadenceError('no_change','A package mapping cannot be unchanged.')
        sch_id=parts[owner['partId']]['schematicId'];group_key=(sch_id,old.casefold())
        if group_key in group_keys:raise CadenceError('duplicate_package_mapping','Each physical base-reference group may appear once.')
        group_keys.add(group_key)
        members=[u for u in units.values() if parts[u['partId']]['schematicId']==sch_id and u['reference'].casefold()==old.casefold()]
        if not members or len(members)>owner['packageSize']:raise CadenceError('ambiguous_package_group','Too many definitions share this package base reference.')
        origin=by_binding.get(owner['partId']);devices=set()
        if origin is None or not all(origin[k] for k in ('isCached','lookupMatchesPlaced','originVerified')):raise CadenceError('cache_binding_unverified','Representative lacks verified cache ownership.')
        for unit in members:
            b=by_binding.get(unit['partId']);suffix=unit['deviceDesignator'];full=old+suffix if owner['packageSize']>1 else old
            if unit['kind']!='placed' or unit['isExternalDesignPart'] or unit['reference']!=old or unit['packageSize']!=owner['packageSize'] or unit['packageName']!=owner['packageName'] or b is None or b['cachePackageId']!=origin['cachePackageId'] or not all(b[k] for k in ('isCached','lookupMatchesPlaced','originVerified')):raise CadenceError('ambiguous_package_group','Every group member must share verified native cache/package ownership.')
            if unit['referenceDesignator']!=full or suffix.casefold() in devices or (owner['packageSize']>1 and not suffix):raise CadenceError('ambiguous_package_group','Full unit references and device suffixes must be unique and consistent.')
            devices.add(suffix.casefold())
        names={new.casefold()}|{(new+u['deviceDesignator']).casefold() for u in members if owner['packageSize']>1}
        if destinations&names:raise CadenceError('reference_conflict','Final package/full-unit names collide with another mapped group.')
        destinations|=names;groups.append({'oldReference':old,'newReference':new,'prefix':before[1],'members':members})
        for unit in members:selected[unit['partId']]=new
    if len(selected)>64:raise CadenceError('mapping_limit','At most64 existing unit instances may be mapped in one task.')
    for unit in units.values():
        if unit['partId'] not in selected and ({unit['reference'].casefold(),unit['referenceDesignator'].casefold()}&destinations):raise CadenceError('reference_conflict','A destination is owned by an unmapped definition or full unit.')
    occupied={s.casefold() for u in units.values() for s in (u['reference'],u['referenceDesignator'])}|destinations;changes=[]
    for group in groups:
        n=900000000
        while n<=999999999:
            temp=group['prefix']+str(n);aliases={temp.casefold()}|{(temp+u['deviceDesignator']).casefold() for u in group['members']}
            if not aliases&occupied:break
            n+=1
        if n>999999999:raise CadenceError('reference_conflict','No bounded temporary base reference is available.')
        occupied|=aliases
        for unit in group['members']:
            changes.append({k:unit[k] for k in ('partId','nativeId','schematicName','pageName','packageName','packageSize','deviceDesignator','sourceLib','sourcePart')}|
                           {'oldReference':unit['reference'],'oldFullReference':unit['referenceDesignator'],'newReference':group['newReference'],
                            'newFullReference':group['newReference']+unit['deviceDesignator'] if unit['packageSize']>1 else group['newReference'],'temporaryReference':temp})
    from .capture_unit_edit import validate_physical_bindings
    validate_physical_bindings({'pin':[p for p in data['pin'] if p['partId'] in selected]},units)
    expected=copy.deepcopy(data)
    for kind in ('part','pin'):
        for row in expected[kind]:
            key=row['objectId'] if kind=='part' else row['partId']
            if key in selected:row['reference']=selected[key]
    return changes,expected

def rename_state_and_units(state,units,changes):
    result=copy.deepcopy(state);new_units=copy.deepcopy(units);by_native={c['nativeId']:c for c in changes}
    for row in result:
        change=by_native.get(row['nativeId'])
        if change is None:continue
        row['reference']=change['newReference'];tokens={change['oldReference']:change['newReference'],change['oldFullReference']:change['newFullReference']}
        for layer in ('effective','user','display'):
            for prop in row[layer]:
                if prop['name'] in REFERENCE_FIELDS:
                    if prop['value'] in tokens:prop['value']=tokens[prop['value']]
                    elif not (layer=='display' and prop['value']==''):raise CadenceError('unsupported_reference_value','A native reference property has an unverified literal/format; do not substitute free text.')
    for u in new_units.values():
        change=by_native.get(u['nativeId'])
        if change:u.update(reference=change['newReference'],referenceDesignator=change['newFullReference'])
    return result,new_units

def nc_owner_graph(data,objects,units):
    result=[];pins={p['objectId']:p for p in data['pin']}
    for obj in objects:
        if obj['kind']!='nc':continue
        a=obj['attributes'];pin=pins.get(a['pinId']);unit=units.get(a['partId'])
        if pin is None or unit is None or pin['partId']!=a['partId'] or pin['number']!=a['number'] or pin['reference']!=a['reference']:raise CadenceError('invalid_nc_owner','NC marker does not match its instance/pin snapshot.')
        result.append([unit['nativeId'],pin['number'],pin['name'],a['hotSpot']])
    return sorted(result,key=lambda r:json.dumps(r,ensure_ascii=False))

def node_reference_table(data,units,changes,after=False):
    selected={c['nativeId']:c for c in changes};rows=[]
    for pin in data['pin']:
        unit=units[pin['partId']];c=selected.get(unit['nativeId'])
        if c is None:continue
        rows.append({'nativeId':unit['nativeId'],'schematicName':unit['schematicName'],'pageName':unit['pageName'],
                     'oldFullReference':c['oldFullReference'],'newFullReference':unit['referenceDesignator'] if after else c['newFullReference'],
                     'number':pin['number'],'name':pin['name'],'connected':pin['connected'],'net':pin['net'] if pin['connected'] else None})
    return sorted(rows,key=lambda r:(r['nativeId'],r['number'],r['name']))

def plan_package_references(writer,sid,mappings):
    with writer.capture.lock:
        cap=writer.capture;session=cap._session(sid);data=session['data'];units=read_units(cap,sid)
        if not isinstance(mappings,list) or not 1<=len(mappings)<=64:raise CadenceError('invalid_reference_map','Declare1..64 package representative mappings.')
        for mapping in mappings:
            if not isinstance(mapping,dict) or mapping.get('partId') not in units:raise CadenceError('object_not_found','Representative is outside this design session.')
            owner=units[mapping['partId']]
            if sum(s['name']==owner['schematicName'] for s in data['schematic'])!=1:raise CadenceError('ambiguous_target','Mapped schematic names must be unique in this definition operation.')
            query_cache_binding(cap,sid,mapping['partId'])
        q=session['qualifiedCache'];changes,expected=package_reference_map(data,units,q['bindings'],mappings)
        state=read_state(writer.config,session['design'],session['design'].parent,units);new_state,new_units=rename_state_and_units(state,units,changes)
        objects=inventory(cap,sid);new_objects=copy.deepcopy(objects);selected={c['partId']:c['newReference'] for c in changes}
        for obj in new_objects:
            if obj['kind']=='nc' and obj['attributes']['partId'] in selected:obj['attributes']['reference']=selected[obj['attributes']['partId']]
        evidence={'state':new_state,'units':unit_graph(new_units),'cacheGroups':cache_groups(q)}
        path=session['design'].parent/(new_id('expected-package-reference')+'.json');write_json(path,evidence)
        payload={'mode':'package_groups_v1','sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'changes':changes,
                 'expectedDefinitionDigest':definition_baseline(expected),'connectionDigest':connection_digest(expected,new_objects),
                 'pinNodeMap':node_reference_table(data,units,changes),
                 'ncOwnerDigest':digest(nc_owner_graph(data,objects,units)),'expectedEvidence':str(path),'expectedEvidenceHash':sha256(path)}
        if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>64000:raise CadenceError('plan_limit','Package reference plan exceeds64KiB.')
        cap._session(sid);return writer.create_plan(payload)

def verify_package_references(writer,d,p,native_completed):
    writer.preflight(p);target=checked_path(str(d/'design.dsn'),(d,));before=sha256(target)
    if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Reference output exceeds128MiB.')
    if native_completed:
        f=d/'native-result.json'
        if f.stat().st_size>4096 or json.loads(f.read_text(encoding='utf-8'))!={'saved':True,'operation':'package_reference_mapping','changed':len(p['changes'])}:raise CadenceError('invalid_worker_result','Package reference receipt differs.')
    evidence=json.loads(checked_path(p['expectedEvidence'],(writer.config.workspace_root,)).read_text(encoding='utf-8'))
    cap=CaptureService(writer.config);cap.workspaces['output']={'directory':d,'manifest':{'copiedFingerprint':before}};sid=cap.open('output')['sessionId']
    try:
        data=cap.sessions[sid]['data'];units=read_units(cap,sid);objects=inventory(cap,sid)
        if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('package_reference_pin_net_mismatch','References or original pin/net mappings differ.','verify')
        if connection_digest(data,objects)!=p['connectionDigest'] or digest(nc_owner_graph(data,objects,units))!=p['ncOwnerDigest']:raise CadenceError('package_reference_connection_mismatch','Connection objects or NC physical ownership changed.','verify')
        if 'pinNodeMap' in p and node_reference_table(data,units,p['changes'],after=True)!=p['pinNodeMap']:raise CadenceError('package_reference_node_table_mismatch','Actual old/new complete unit pin/node table differs from the frozen mapping.','verify')
        state=read_state(writer.config,target,d,units)
        if state!=evidence['state'] or unit_graph(units)!=evidence['units']:raise CadenceError('package_reference_state_mismatch','Unit ownership, geometry or modeled property/display state differs.','verify')
        for change in p['changes']:
            matches=[u for u in units.values() if u['nativeId']==change['nativeId']]
            if len(matches)!=1:raise CadenceError('package_reference_identity_mismatch','A mapped native unit is missing.')
            query_cache_binding(cap,sid,matches[0]['partId'])
        if cache_groups(cap.sessions[sid]['qualifiedCache'])!=evidence['cacheGroups']:raise CadenceError('package_reference_cache_changed','Reference mapping changed source-qualified cache definitions.','verify')
    finally:cap.close(sid)
    writer.preflight(p)
    if sha256(target)!=before:raise CadenceError('target_changed','Reference output changed during verification.')
    ident=d.name.removeprefix('plan-');artifact={'artifactId':'package-references-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
    return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'referenceMap':p['changes'],'sourceModified':False,
            'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'packageOwnershipVerified':True,'modeledAllInstanceStateVerified':True,'cacheMetadataPreserved':True,'ncOwnershipPreserved':True,'oldNewNodeTableVerified':'pinNodeMap' in p,'pinNodeMap':p.get('pinNodeMap',[]),
            'outputWorkspaceRelativePath':d.relative_to(writer.config.workspace_root).as_posix(),'scope':'explicit_schematic_definition_package_reference_groups',
            'notChecked':['occurrence_reference_mapping','native_automatic_annotation','unnumbered_allocation','display_font_and_render','unrelated_cache_vector_graphics','native_drc','electrical_behavior']}
