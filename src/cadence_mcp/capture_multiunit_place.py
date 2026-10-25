"""Atomic complete-package placement with unit-scoped pin and source-view identity."""
import copy,json,re,shutil,uuid
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_place import CapturePlacements,validate_pins
from .capture_geometry import read_part_geometry
from .capture_part_edit import geometry_row
from .capture_properties import read_part_properties
from .capture_references import read_units
from .capture_wire import inventory,connection_digest,point
from .core import CadenceError,checked_path,sha256,write_json
from .environment import ADAPTERS,process_env,run_tcl
from .process_tree import run_owned_process
from .embedded_tcl import command as embedded_command

def select_units(data,units):
    if not isinstance(units,list) or not 2<=len(units)<=16:raise CadenceError('invalid_group','Declare 2..16 units of one complete source package.')
    selected=[];seen=set();package_id=None;total=0
    for unit in units:
        if not isinstance(unit,dict) or set(unit)!={'libraryPartId','location','rotationCode','mirrorCode','expectedPins'}:raise CadenceError('invalid_group','Invalid typed unit declaration.')
        if not point(unit['location']) or type(unit['rotationCode']) is not int or unit['rotationCode'] not in range(4) or type(unit['mirrorCode']) is not int or unit['mirrorCode'] not in (0,1):raise CadenceError('invalid_placement','Invalid declared unit pose.')
        part=next((p for p in data['part'] if p['objectId']==unit['libraryPartId']),None)
        if part is None:raise CadenceError('object_not_found','Selected unit part is outside the library session.')
        device=next(d for d in data['device'] if d['objectId']==part['deviceId']);cell=next(c for c in data['cell'] if c['objectId']==part['cellId'])
        if package_id is None:package_id=part['packageId']
        if part['packageId']!=package_id or device['objectId'] in seen:raise CadenceError('invalid_group','Every source device must appear exactly once in one package.')
        if not re.fullmatch(r'[A-Za-z0-9]{1,8}',device['designator']):raise CadenceError('unsupported_designator','A multiunit source needs distinct nonempty bounded device designators.')
        seen.add(device['objectId']);source=[p for p in data['pin'] if p['partId']==part['objectId']];validate_pins(source,unit['expectedPins']);total+=len(source)
        if total>512:raise CadenceError('input_limit','The complete group exceeds 512 logical pin rows.')
        selected.append({'deviceDesignator':device['designator'],'devicePosition':device['position'],'cellName':cell['name'],'partName':part['name'],'sourceCellPartCount':sum(p['cellId']==cell['objectId'] for p in data['part']),'location':unit['location'],'rotation':unit['rotationCode'],'mirror':unit['mirrorCode'],'expectedPins':copy.deepcopy(unit['expectedPins'])})
    all_devices={d['objectId'] for d in data['device'] if d['packageId']==package_id}
    if seen!=all_devices or len({u['deviceDesignator'].casefold() for u in selected})!=len(selected):raise CadenceError('incomplete_group','The declaration must cover every source device with distinct designators.')
    physical={}
    for unit in selected:
        for pin in unit['expectedPins']:
            binding=(pin['connected'],pin['net'].casefold() if pin['connected'] else None)
            if pin['number'] in physical and physical[pin['number']]!=binding:raise CadenceError('shared_pin_binding_conflict','One physical package pad cannot have contradictory unit net expectations; unresolved local/flat shared bindings require explicit verification.')
            physical[pin['number']]=binding
    return next(p for p in data['package'] if p['objectId']==package_id),selected

def existing_definitions(data,page_id,rows):
    pins={p['objectId']:p for p in data['pin'] if p['pageId']==page_id};supplied={}
    if not isinstance(rows,list) or len(rows)>2048:raise CadenceError('invalid_expectations','Bound existing pin expectations to 2048 rows.')
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'pinId','connected','net'} or not isinstance(row['pinId'],str) or row['pinId'] not in pins or row['pinId'] in supplied or type(row['connected']) is not bool:raise CadenceError('invalid_expectations','Existing pins need unique revision-bound pin IDs.')
        if row['connected']:
            if not isinstance(row['net'],str) or not 1<=len(row['net'])<=512 or '\x00' in row['net']:raise CadenceError('invalid_expectations','Connected pins need a bounded explicit net name.')
        elif row['net'] is not None:raise CadenceError('invalid_expectations','Unbound pins require null net.')
        supplied[row['pinId']]=row
    if supplied.keys()!=pins.keys():raise CadenceError('incomplete_expectations','Declare every existing pin of the selected page exactly once.')
    expected=copy.deepcopy(data)
    for p in expected['pin']:
        if p['objectId'] in supplied:p.update(connected=supplied[p['objectId']]['connected'],net=supplied[p['objectId']]['net'] or '')
    return expected

class CaptureMultiunitPlacements(CapturePropertyEdits):
    kind='capture_multiunit_placement'
    max_record_bytes=262144
    def __init__(self,config,capture,library):super().__init__(config,capture);self.library=library
    def preflight(self,p):
        if p.get('operation')=='add_cached_unit':
            source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
            if not source.is_file() or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Cached-unit source design changed after planning.')
        else:CapturePlacements.preflight(self,p)
    def plan_add(self,sid,owner_id,cache_part_id,location,rotation,mirror,pins,connections,target_page_id=None):
        from .capture_cached_unit_add import plan_cached_unit
        return plan_cached_unit(self,sid,owner_id,cache_part_id,location,rotation,mirror,pins,connections,target_page_id)
    def plan(self,sid,page_id,lid,reference,value,units,connections):
        if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z][A-Za-z_]*[1-9][0-9]{0,8}',reference) or len(reference)>64:raise CadenceError('invalid_reference','Declare one numbered package base reference.')
        if not isinstance(value,str) or len(value)>1024 or '\x00' in value:raise CadenceError('invalid_value','Invalid shared package value.')
        with self.capture.lock,self.library.lock:
            session=self.capture._session(sid);lib=self.library._session(lid);data=session['data'];package,chosen=select_units(lib['data'],units);page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('object_not_found','Target page is outside this session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity is not unique.')
            identities=read_units(self.capture,sid);reserved={reference.casefold()}|{(reference+u['deviceDesignator']).casefold() for u in chosen}
            if any(row[k].casefold() in reserved for row in identities.values() for k in ('reference','referenceDesignator')):raise CadenceError('reference_conflict','The base or full unit reference is already owned by the design.')
            expected=existing_definitions(data,page_id,connections);oldparts=[p for p in data['part'] if p['pageId']==page_id]
            if len(oldparts)>100:raise CadenceError('input_limit','Bound original-page geometry verification to 100 parts.')
            old_geometry=[{'nativeId':identities[p['objectId']]['nativeId'],'reference':p['reference'],'referenceDesignator':identities[p['objectId']]['referenceDesignator'],'geometry':geometry_row(read_part_geometry(self.capture,sid,p['objectId']))} for p in oldparts]
            for u in chosen:
                oid='planned-'+u['deviceDesignator'];expected['part'].append({'objectId':oid,'pageId':page_id,'schematicId':page['schematicId'],'reference':reference})
                for i,p in enumerate(u['expectedPins']):expected['pin'].append({'objectId':oid+'/pin-'+str(i),'partId':oid,'pageId':page_id,'schematicId':page['schematicId'],'reference':reference,'number':p['number'],'name':p['name'],'connected':p['connected'],'net':p['net'] or ''})
            objects=inventory(self.capture,sid)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'sourceLibrary':str(lib['directory']/'library.olb'),'libraryFingerprint':lib['revision'],'schematicName':sch['name'],'pageName':page['name'],'packageName':package['name'],'expectedFootprint':package['footprint'],'cacheName':'MCP_'+uuid.uuid4().hex[:20],'reference':reference,'value':value,'units':chosen,'oldPageGeometry':old_geometry,'expectedDefinitionDigest':definition_baseline(expected),'expectedConnectionDigest':connection_digest(data,objects)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>160000:raise CadenceError('plan_limit','Group plan exceeds its durable size bound.')
            self.capture._session(sid);self.library._session(lid);return self.create_plan(payload)
    def preview(self,p):
        if p.get('operation')=='add_cached_unit':return {k:p[k] for k in ('operation','reference','cacheName','ownerNativeId','deviceDesignator','partName','location','rotation','mirror','expectedPins','value','footprint','sourceFingerprint')}
        return {k:p[k] for k in ('reference','value','schematicName','pageName','packageName','cacheName','units','sourceFingerprint','libraryFingerprint')}
    def execute(self,directory,p,cancel,on_started):
        if p.get('operation')=='add_cached_unit':
            from .capture_cached_unit_add import execute_cached_unit
            return execute_cached_unit(self,directory,p,cancel,on_started)
        self.preflight(p)
        for key,name,fp in [('sourceDesign','design.dsn','sourceFingerprint'),('sourceLibrary','library.olb','libraryFingerprint')]:
            source=checked_path(p[key],(self.config.workspace_root,))
            with source.open('rb') as original,(directory/name).open('xb') as target:shutil.copyfileobj(original,target)
            if sha256(directory/name)!=p[fp] or sha256(source)!=p[fp]:raise CadenceError('target_changed','Group source changed during copy.')
        with (directory/'group-request.json').open('x',encoding='utf-8') as request:json.dump(p,request,ensure_ascii=False,separators=(',',':'))
        return run_owned_process(embedded_command(self.config.install_root,'edit_multiunit_place.tcl',[directory/'design.dsn',directory/'library.olb',directory/'group-request.json',directory/'native-result.json']),directory,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def verify(self,directory,p,native_completed):
        if p.get('operation')=='add_cached_unit':
            from .capture_cached_unit_add import verify_cached_unit
            return verify_cached_unit(self,directory,p,native_completed)
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024 or sha256(directory/'library.olb')!=p['libraryFingerprint']:raise CadenceError('target_changed','Invalid group output or private source library.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'reference':p['reference'],'cacheName':p['cacheName'],'unitCount':len(p['units'])}:raise CadenceError('invalid_worker_result','Group save receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}};sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('group_definition_mismatch','Saved unit pin definitions or bindings differ from the complete frozen expectation.','verify')
            if connection_digest(data,inventory(verifier,sid))!=p['expectedConnectionDigest']:raise CadenceError('group_connection_objects_changed','Placement changed connection geometry or labels.','verify')
            identities=read_units(verifier,sid);selected=[r for r in identities.values() if r['reference']==p['reference']]
            if len(selected)!=len(p['units']):raise CadenceError('group_identity_mismatch','The group does not contain exactly the declared units.')
            for unit in p['units']:
                matches=[r for r in selected if r['deviceDesignator']==unit['deviceDesignator'] and r['referenceDesignator']==p['reference']+unit['deviceDesignator'] and r['packageName']==p['cacheName'] and r['packageSize']==len(p['units']) and r['kind']=='placed' and not r['isExternalDesignPart'] and r['schematicName']==p['schematicName'] and r['pageName']==p['pageName']]
                if len(matches)!=1:raise CadenceError('group_identity_mismatch','Unit ownership or full reference differs from the declaration.')
                part=matches[0];geom=geometry_row(read_part_geometry(verifier,sid,part['partId']));wanted={'location':unit['location'],'rotationCode':unit['rotation'],'mirrorCode':unit['mirror'],'pins':sorted([{k:pin[k] for k in ('number','name','hotSpot')} for pin in unit['expectedPins']],key=lambda q:(q['number'],q['name']))}
                if geom!=wanted:raise CadenceError('group_hotspot_mismatch','Saved unit pose or global pin hotspots differ from its oracle.')
                pins=[q for q in data['pin'] if q['partId']==part['partId']]
                if sorted((q['number'],q['name'],q['connected'],q['net']) for q in pins)!=sorted((q['number'],q['name'],q['connected'],q['net'] or '') for q in unit['expectedPins']):raise CadenceError('group_unit_binding_mismatch','Unit-scoped physical pin bindings differ; shared numbers are not interchangeable.')
                props={q['name']:q['value'] for q in read_part_properties(verifier,sid,part['partId'])['items']}
                if props.get('Value')!=p['value'] or props.get('PCB Footprint')!=p['expectedFootprint']:raise CadenceError('group_property_mismatch','A unit lost its shared value or inherited footprint.')
                out=directory/('view-'+unit['deviceDesignator']+'.json')
                if out.exists():out.unlink()
                run_tcl(self.config,'inspect_placed_view.tcl',[str(target),str(directory/'library.olb'),str(out),p['schematicName'],p['pageName'],p['reference'],p['packageName'],unit['deviceDesignator'],unit['partName']],directory)
                if json.loads(out.read_text(encoding='utf-8')).get('matches') is not True:raise CadenceError('group_view_mismatch','A saved unit uses a different source pin/line view.')
            network_result=directory/'native-page-bindings.json'
            if network_result.exists():network_result.unlink()
            run_tcl(self.config,'inspect_net_symbol_bindings.tcl',[str(target),str(network_result)],directory)
            bindings=json.loads(network_result.read_text(encoding='utf-8'));net_groups={}
            for unit in p['units']:
                for pin in unit['expectedPins']:
                    rows=[b for b in bindings if b['kind']=='pin' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and b['reference']==p['reference']+unit['deviceDesignator'] and b['number']==pin['number'] and b['name']==pin['name']]
                    if len(rows)!=1 or (rows[0]['group'] is not None)!=pin['connected'] or rows[0]['netName']!=(pin['net'] or ''):raise CadenceError('group_native_binding_mismatch','A unit pin differs from its native object-binding expectation.')
                    if pin['connected']:net_groups.setdefault(pin['net'],set()).add(rows[0]['group'])
            for name,groups in net_groups.items():
                groups.update(b['group'] for b in bindings if b['kind']=='wire' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and b['netName']==name)
                if len(groups)!=1 or None in groups:raise CadenceError('group_native_network_mismatch','Declared pin/wire network members do not share one native object.')
            if len({next(iter(g)) for g in net_groups.values()})!=len(net_groups):raise CadenceError('group_native_network_mismatch','Distinct declared nets unexpectedly share a native object.')
            for old in p['oldPageGeometry']:
                rows=[r for r in identities.values() if r['nativeId']==old['nativeId'] and r['reference']==old['reference'] and r['referenceDesignator']==old['referenceDesignator'] and r['pageName']==p['pageName'] and r['schematicName']==p['schematicName']]
                if len(rows)!=1 or geometry_row(read_part_geometry(verifier,sid,rows[0]['partId']))!=old['geometry']:raise CadenceError('group_original_geometry_changed','An original page instance or pin hotspot changed.')
        finally:verifier.close(sid)
        if sha256(target)!=before or sha256(directory/'library.olb')!=p['libraryFingerprint']:raise CadenceError('target_changed','Group output changed during verification.')
        self.preflight(p);ident=directory.name.removeprefix('plan-');artifact={'artifactId':'multiunit-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'unitCount':len(p['units']),'unitOwnershipVerified':True,'sourcePinLineViewsVerified':True,'sourceVectorGeometryVerified':True,'unitPinBindingsVerified':True,'nativePageNetworksVerified':True,'originalPageGeometryVerified':True,'sourceModified':False,'libraryModified':False,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['incremental_group_edit','flat_occurrence_connectivity','non_line_graphics','external_cache_closure','native_drc','rendered_layout']}
