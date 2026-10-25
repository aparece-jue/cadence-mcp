"""Source-qualified DSN cache identity reads; no external library file is opened."""
import copy,json
from .core import CadenceError,checked_path,new_id
from .environment import run_tcl
from .library import validate_library
from .capture_references import read_units

def validate_cache_bindings(snapshot,design,units):
    try:
        if not isinstance(snapshot,dict) or set(snapshot)!={'definitions','origins','bindings'}:raise ValueError('shape')
        data=snapshot['definitions'];validate_library(data)
        packages={r['objectId']:r for r in data['package']};origins=snapshot['origins'];bindings=snapshot['bindings']
        if not isinstance(origins,list) or len(origins)!=len(packages) or not isinstance(bindings,list) or len(bindings)>len(design['part']):raise ValueError('count')
        seen=set();by_origin={}
        for row in origins:
            if set(row)!={'cachePackageId','isCached','sourceLibrary','originVerified'} or row['cachePackageId'] not in packages or row['cachePackageId'] in seen:raise ValueError('origin identity')
            if any(type(row[k]) is not bool for k in ('isCached','originVerified')) or not isinstance(row['sourceLibrary'],str) or len(row['sourceLibrary'])>32768:raise ValueError('origin fields')
            if row['isCached'] and (not row['originVerified'] or not row['sourceLibrary']):raise ValueError('unverified cached origin')
            seen.add(row['cachePackageId']);by_origin[row['cachePackageId']]=row
        if seen!=set(packages):raise ValueError('missing origins')
        parts={r['objectId']:r for r in design['part']};schematics={r['objectId']:r['name'] for r in design['schematic']};pages={r['objectId']:r for r in design['page']};seen=set()
        fields={'partId','nativeId','schematicName','pageName','reference','cachePackageId','sourceLibrary','sourcePackage','sourcePart','deviceDesignator','isCached','lookupMatchesPlaced','originVerified'}
        if set(units)!=set(parts):raise ValueError('independent instance coverage')
        placed={key:value for key,value in units.items() if value['kind']=='placed'}
        if len(bindings)!=len(placed):raise ValueError('placed instance coverage')
        devices=data['device'];library_parts=data['part']
        for row in bindings:
            if not isinstance(row,dict) or set(row)!=fields or row['partId'] not in parts or row['partId'] in seen or row['cachePackageId'] not in packages:raise ValueError('binding identity')
            if type(row['nativeId']) is not int or row['nativeId']<0 or any(type(row[k]) is not bool for k in ('isCached','lookupMatchesPlaced','originVerified')):raise ValueError('binding flags')
            if any(not isinstance(row[k],str) or len(row[k])>32768 for k in ('schematicName','pageName','reference','sourceLibrary','sourcePackage','sourcePart','deviceDesignator')):raise ValueError('binding strings')
            part=parts[row['partId']];page=pages[part['pageId']]
            if (row['schematicName'],row['pageName'],row['reference'])!=(schematics[part['schematicId']],page['name'],part['reference']):raise ValueError('target scope')
            origin=by_origin[row['cachePackageId']];pkg=packages[row['cachePackageId']]
            unit=placed.get(row['partId'])
            if unit is None or row['nativeId']!=unit['nativeId'] or row['sourceLibrary'].casefold()!=unit['sourceLib'].casefold() or row['sourcePart']!=unit['sourcePart'] or row['deviceDesignator']!=unit['deviceDesignator'] or pkg['name']!=unit['packageName']:raise ValueError('independent native instance identity')
            if row['isCached']!=origin['isCached']:raise ValueError('cache kind')
            if row['lookupMatchesPlaced'] and (not row['originVerified'] or not row['isCached'] or not row['sourceLibrary'] or row['sourceLibrary'].casefold()!=origin['sourceLibrary'].casefold() or row['sourcePackage']!=pkg['name']):raise ValueError('qualified origin mismatch')
            matches=[d for d in devices if d['packageId']==pkg['objectId'] and d['designator']==row['deviceDesignator']]
            if len(matches)!=1 or not any(p['deviceId']==matches[0]['objectId'] and p['name']==row['sourcePart'] for p in library_parts):raise ValueError('source device/view mismatch')
            seen.add(row['partId'])
        return copy.deepcopy(snapshot)
    except (ValueError,TypeError,KeyError,AttributeError) as error:
        raise CadenceError('invalid_cache_binding_snapshot','Native cache definitions, origins and placed instance bindings must agree completely.') from error

def query_cache_binding(capture,sid,part_id):
    with capture.lock:
        session=capture._session(sid)
        if not any(p['objectId']==part_id for p in session['data']['part']):raise CadenceError('object_not_found','Part is outside this immutable design session.')
        if 'qualifiedCache' not in session:
            directory=checked_path(str(capture._workspace(session['workspaceId'])['directory']),(capture.config.workspace_root,))
            output=directory/(new_id('cache-bindings')+'.json')
            run_tcl(capture.config,'inspect_cache_bindings.tcl',[str(session['design']),str(output),'100000'],directory)
            capture._session(sid)
            if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Qualified cache snapshot exceeds32MiB.')
            units=read_units(capture,sid)
            try:snapshot=validate_cache_bindings(json.loads(output.read_text(encoding='utf-8')),session['data'],units)
            except (ValueError,UnicodeError) as error:raise CadenceError('invalid_worker_result','Invalid cache binding JSON.') from error
            if 'cacheDefinitions' in session and session['cacheDefinitions']!=snapshot['definitions']:
                raise CadenceError('cache_snapshot_identity_changed','Cache traversal identities differ from an earlier query; create a fresh session before mixing identities.')
            session['qualifiedCache']=snapshot;session.setdefault('cacheDefinitions',snapshot['definitions']);session.setdefault('cacheCursors',{});output.unlink()
        snapshot=session['qualifiedCache'];rows=[r for r in snapshot['bindings'] if r['partId']==part_id]
        if not rows:raise CadenceError('not_placed_instance','A drawn/hierarchical instance has no placed package cache binding.')
        row=rows[0]
        if not all(row[k] for k in ('isCached','lookupMatchesPlaced','originVerified')):raise CadenceError('cache_binding_unverified','Placed package does not have a verified source-qualified cache identity.')
        package=next(p for p in snapshot['definitions']['package'] if p['objectId']==row['cachePackageId'])
        selected={k:[r for r in values if (r['objectId'] if k=='package' else r['packageId'])==row['cachePackageId']] for k,values in snapshot['definitions'].items()}
        # Scope fields select the exact native package; same-name local definitions remain distinct.
        same_name=[dict(o,packageName=p['name']) for p in snapshot['definitions']['package'] if p['name']==package['name'] for o in snapshot['origins'] if o['cachePackageId']==p['objectId']]
        capture._session(sid)
        return {'sessionId':sid,'revision':session['revision'],'partId':part_id,'binding':copy.deepcopy(row),'definitions':copy.deepcopy(selected),'sameNameDefinitions':copy.deepcopy(same_name),
                'scope':'source_qualified_placed_package_cache','sourceQualifiedPackageIdentityVerified':True,'externalSourceLibraryVerified':False,'cacheSynchronizationVerified':False,'readOnly':True,
                'notChecked':['external_library_file_identity','cache_write_or_replacement','override_inheritance_policy','occurrence_connectivity','rendered_appearance','native_drc']}
