"""Bound scalar symbol edits and terminal poses with native page partitions."""
import copy,json,re
from .capture_alias_edit import CaptureAliasEdits,definition_structure
from .capture_part_edit import page_geometry
from .capture_wire import inventory,connection_digest,point_on_path,point
from .page_net_partition import page_partition
from .isolated_jobs import digest
from .core import CadenceError,new_id,write_json,sha256
from .environment import ADAPTERS,run_tcl

def binding_rows(capture,sid):
    s=capture._session(sid);d=capture._workspace(s['workspaceId'])['directory'];out=d/(new_id('symbol-bindings')+'.json')
    run_tcl(capture.config,'inspect_net_symbol_bindings.tcl',[str(s['design']),str(out)],d);capture._session(sid)
    if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Symbol binding evidence exceeds limit.')
    rows=json.loads(out.read_text(encoding='utf-8'));page_partition([r for r in rows if r['kind'] in ('pin','wire')]);out.unlink();return rows

def symbol_metadata(config,design,directory,schematic,page,kind,native_id,name,hotspot):
    out=directory/(new_id('symbol-metadata')+'.json')
    run_tcl(config,'inspect_net_symbol_metadata.tcl',[str(design),str(out),schematic,page,kind,str(native_id),name,*map(str,hotspot)],directory)
    if out.stat().st_size>4*1024*1024:raise CadenceError('output_limit','Symbol metadata exceeds limit.')
    data=json.loads(out.read_text(encoding='utf-8'));out.unlink()
    if set(data)!={'nativeId','metadata'} or type(data['nativeId']) is not int or set(data['metadata'])!={'user','effective','display'} or any(not isinstance(rows,list) for rows in data['metadata'].values()):raise CadenceError('invalid_worker_result','Invalid symbol metadata snapshot.')
    return data

def expected_symbol_metadata(metadata,location,rebind):
    expected=copy.deepcopy(metadata)
    if rebind:
        sources=[p for p in expected['effective'] if p['name']=='Source Library']
        if len(sources)!=1 or not sources[0]['value'].casefold().endswith('.dsn'):raise CadenceError('unsupported_symbol_source_rebind','Recreation currently requires an existing DSN cache-source binding.')
        sources[0]['value']='__OWNED_OUTPUT_CACHE__'
    for prop in expected['effective']:
        if prop['name']=='Location X-Coordinate':prop['value']=str(location[0])
        if prop['name']=='Location Y-Coordinate':prop['value']=str(location[1])
    return expected

def symbol_changes(objects,target,operation,name):
    if operation not in ('set_name','delete'):raise CadenceError('invalid_net_symbol_edit','Use set_name or delete; pose lifecycle has unresolved native gates.')
    if target['kind'] not in ('global','offpage') or target['attributes']['isBus']:raise CadenceError('unsupported_net_symbol','Only scalar global/offpage symbols are supported.')
    if operation=='delete':
        if name is not None:raise CadenceError('invalid_net_symbol_edit','Deletion has no new name.')
    else:
        if not isinstance(name,str) or not re.fullmatch(r'[^\s\[\]\x00-\x1f\x7f]{1,128}',name):raise CadenceError('invalid_net_symbol_name','Use a bounded scalar identifier.')
        if name==target['attributes']['name']:raise CadenceError('no_change','Symbol name already matches.')
    changed=copy.deepcopy(objects)
    if operation=='delete':changed=[o for o in changed if o['objectId']!=target['objectId']]
    else:next(o for o in changed if o['objectId']==target['objectId'])['attributes']['name']=name
    return changed

def symbol_name_conflicts(objects,symbol_id,wire_id,name):
    """Capture ignores case for electrical names; guard all known connection definitions."""
    key=name.casefold()
    return any(o['objectId'] not in (symbol_id,wire_id)
               and isinstance(o['attributes'].get('name',o['attributes'].get('net')),str)
               and o['attributes'].get('name',o['attributes'].get('net')).casefold()==key
               for o in objects if o['kind'] in ('wire','global','offpage','alias','port'))

def symbol_pose_changes(objects,target,wire,location,rotation,mirror,hotspot,pin_hotspots):
    if target['attributes']['isBus'] or not point(location) or not point(hotspot) or type(rotation) is not int or rotation not in range(4) or type(mirror) is not int or mirror not in (0,1):raise CadenceError('invalid_net_symbol_pose','Declare scalar symbol location, rotation0..3, mirror0..1 and independent saved hotspot.')
    old=target['attributes'];path=wire['attributes']['points']
    if len(path)!=2 or path[0]==path[1] or old['hotSpot'] not in path:raise CadenceError('unsupported_symbol_lead','Pose editing requires a two-point terminal lead.')
    if (location,rotation,mirror)==(old['location'],old['rotationCode'],old['mirrorCode']):raise CadenceError('no_change','Symbol pose already matches.')
    index=path.index(old['hotSpot']);new_path=copy.deepcopy(path);new_path[index]=hotspot
    if new_path[0]==new_path[1] or (new_path[0][0]!=new_path[1][0] and new_path[0][1]!=new_path[1][1]):raise CadenceError('unsupported_symbol_lead','Keep a nonempty orthogonal scalar lead.')
    if hotspot!=old['hotSpot']:
        if old['hotSpot'] in pin_hotspots:raise CadenceError('symbol_lead_dependency','Another physical pin anchors the moving endpoint.')
        for obj in objects:
            if obj['pageId']!=target['pageId'] or obj['objectId'] in (target['objectId'],wire['objectId']):continue
            attrs=obj['attributes']
            if (obj['kind']=='wire' and point_on_path(old['hotSpot'],attrs['points'])) or attrs.get('hotSpot')==old['hotSpot'] or attrs.get('location')==old['hotSpot']:raise CadenceError('symbol_lead_dependency','Another connection object anchors the moving endpoint.')
    for obj in objects:
        if obj['kind']=='alias' and obj['attributes']['wireId']==wire['objectId'] and not point_on_path(obj['attributes']['location'],new_path):raise CadenceError('symbol_lead_dependency','A wire alias would leave its owning lead.')
    changed=copy.deepcopy(objects)
    next(o for o in changed if o['objectId']==target['objectId'])['attributes'].update(location=location,rotationCode=rotation,mirrorCode=mirror,hotSpot=hotspot)
    next(o for o in changed if o['objectId']==wire['objectId'])['attributes']['points']=new_path
    return changed,{'location':location,'rotation':rotation,'mirror':mirror,'expectedHotSpot':hotspot,'oldWirePoints':copy.deepcopy(path),'newWirePoints':new_path,'wireEndIndex':index}

class CaptureNetSymbolEdits(CaptureAliasEdits):
    kind='capture_net_symbol_edit'
    def plan(self,sid,symbol_id,wire_id,operation,name=None,expected_wire_net=None,location=None,rotation=None,mirror=None,expected_hotspot=None,allow_source_cache_rebind=False):
        if type(allow_source_cache_rebind) is not bool:raise CadenceError('invalid_net_symbol_edit','Source cache rebinding requires an explicit Boolean policy.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];objects=inventory(self.capture,sid)
            target=next((o for o in objects if o['objectId']==symbol_id and o['kind'] in ('global','offpage')),None)
            if target is None:raise CadenceError('object_not_found','Global/offpage target is outside this session.')
            old=target['attributes'];pose=None
            if operation!='set_pose':
                if allow_source_cache_rebind or any(v is not None for v in (location,rotation,mirror,expected_hotspot)):raise CadenceError('invalid_net_symbol_edit','Only set_pose accepts pose declarations.')
                changed=symbol_changes(objects,target,operation,name)
            elif name is not None:raise CadenceError('invalid_net_symbol_edit','Pose preserves the original symbol name.')
            page=next(p for p in data['page'] if p['objectId']==target['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page must be unique.')
            wire=next((o for o in objects if o['objectId']==wire_id and o['kind']=='wire' and o['pageId']==page['objectId']),None)
            if wire is None or not point_on_path(old['hotSpot'],wire['attributes']['points']):raise CadenceError('invalid_symbol_wire','Provide the existing target wire at the symbol hotspot.')
            geometry=page_geometry(self.capture,sid,page['objectId'])
            if operation=='set_pose':
                changed,pose=symbol_pose_changes(objects,target,wire,location,rotation,mirror,expected_hotspot,[pin['hotSpot'] for part in geometry.values() for pin in part['pins']])
                pose['recreate']=target['kind']=='offpage' and (rotation,mirror)!=(old['rotationCode'],old['mirrorCode'])
                if pose['recreate'] and not allow_source_cache_rebind:raise CadenceError('offpage_pose_rebind_required','Offpage orientation reconstruction requires explicit rebinding to the output design cache.')
                if allow_source_cache_rebind and not pose['recreate']:raise CadenceError('invalid_net_symbol_edit','Cache rebinding is only used for offpage orientation reconstruction.')
                pose['sourceCacheRebind']=allow_source_cache_rebind
            if operation=='set_name' and symbol_name_conflicts(objects,symbol_id,wire_id,name):raise CadenceError('net_symbol_merge_unsupported','Name already exists in another connection object; explicit network merge is required.')
            rows=binding_rows(self.capture,sid);scope=(sch['name'],page['name']);key=[*scope,wire['nativeId']]
            symbols=[r for r in rows if r['kind']==target['kind'] and (r['schematicName'],r['pageName'])==scope and r['name']==old['name'] and r['hotSpot']==old['hotSpot']]
            wires=[r for r in rows if r['kind']=='wire' and [r['schematicName'],r['pageName'],r['nativeId']]==key]
            if len(symbols)!=1 or len(wires)!=1 or symbols[0]['group'] is None or symbols[0]['group']!=wires[0]['group']:raise CadenceError('net_symbol_binding_mismatch','Target symbol and declared wire must share one native page net.')
            owner=expected_wire_net if expected_wire_net is not None else name if operation=='set_name' else wire['attributes']['net'] if operation=='set_pose' else None
            if owner is not None and (not isinstance(owner,str) or not 1<=len(owner)<=512 or re.search(r'[\x00-\x1f\x7f]',owner)):raise CadenceError('invalid_net_name','Invalid explicit saved wire net expectation.')
            expected_rows=copy.deepcopy([r for r in rows if r['kind'] in ('pin','wire')])
            if pose is not None:next(r for r in expected_rows if r['kind']=='wire' and [r['schematicName'],r['pageName'],r['nativeId']]==key)['points']=pose['newWirePoints']
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'symbolId':symbol_id,'wireId':wire_id,'kind':target['kind'],'nativeId':target['nativeId'],'schematicName':scope[0],'pageName':scope[1],'oldName':old['name'],'oldLocation':old['location'],'oldHotSpot':old['hotSpot'],'oldRotation':old['rotationCode'],'oldMirror':old['mirrorCode'],'operation':operation,'name':name or '', 'wireNativeId':wire['nativeId'],'expectedWireNet':owner,'partitionDigest':digest(page_partition(expected_rows,key)),'expectedDefinitionDigest':definition_structure(data),'connectionDigest':connection_digest(data,changed),'expectedGeometry':geometry}
            if pose is not None:payload['pose']=pose
            if pose is not None:
                metadata=symbol_metadata(self.config,session['design'],session['design'].parent,*scope,target['kind'],target['nativeId'],old['name'],old['hotSpot'])['metadata']
                payload['expectedSymbolMetadata']=expected_symbol_metadata(metadata,location,allow_source_cache_rebind)
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Symbol plan exceeds durable limit.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('symbolId','wireId','kind','schematicName','pageName','oldName','oldLocation','oldHotSpot','operation','name','expectedWireNet','sourceFingerprint')}|({'pose':p['pose']} if 'pose' in p else {})
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);write_json(d/'symbol-edit.json',{k:p[k] for k in ('kind','nativeId','schematicName','pageName','oldName','oldLocation','oldHotSpot','oldRotation','oldMirror','operation','name')}|({'pose':p['pose'],'wireNativeId':p['wireNativeId']} if 'pose' in p else {}))
        # Bypass the alias-specific request writer while retaining the owned copy/job implementation.
        from .capture_edit import CapturePropertyEdits
        return CapturePropertyEdits.execute(self,d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_net_symbol_name.tcl',self.config.install_root,d/'design.dsn',d/'symbol-edit.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        result=super().verify(d,p,native_completed)
        if p['operation'] in ('set_name','set_pose'):
            target=d/'design.dsn';out=d/(new_id('symbol-binding')+'.json');before=sha256(target)
            if before!=result['artifact']['sha256']:raise CadenceError('target_changed','Symbol output changed between verification stages.')
            run_tcl(self.config,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],d)
            if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Symbol binding evidence exceeds limit.')
            rows=json.loads(out.read_text(encoding='utf-8'));scope=(p['schematicName'],p['pageName'])
            symbols=[r for r in rows if r['kind']==p['kind'] and (r['schematicName'],r['pageName'])==scope and r['name']==(p['oldName'] if p['operation']=='set_pose' else p['name']) and r['hotSpot']==(p['pose']['expectedHotSpot'] if p['operation']=='set_pose' else p['oldHotSpot'])]
            wires=[r for r in rows if r['kind']=='wire' and (r['schematicName'],r['pageName'])==scope and r['nativeId']==p['wireNativeId']]
            if len(symbols)!=1 or len(wires)!=1 or symbols[0]['group'] is None or symbols[0]['group']!=wires[0]['group']:raise CadenceError('net_symbol_binding_mismatch','Renamed symbol lost its declared native wire binding.')
            if sha256(target)!=before:raise CadenceError('target_changed','Symbol binding read changed output.')
            self.preflight(p)
        result.update(scope='scalar_net_symbol_name_delete_preserve_page_membership',symbolKind=p['kind'],occurrenceConnectivityVerified=False)
        result['artifact']['artifactId']='net-symbol-edit-'+d.name.removeprefix('plan-')
        result['notChecked']=['symbol_pose_lifecycle','cross_page_global_offpage_flat_connectivity','occurrence_flat_nets','other_page_geometry','other_part_properties','rendering','native_drc']
        if p['operation']=='set_pose':
            result['scope']='scalar_net_symbol_pose_terminal_lead_preserve_page_membership'
            result['notChecked'].remove('symbol_pose_lifecycle')
            before=sha256(d/'design.dsn')
            actual=symbol_metadata(self.config,d/'design.dsn',d,p['schematicName'],p['pageName'],p['kind'],0 if p['pose']['recreate'] else p['nativeId'],p['oldName'],p['pose']['expectedHotSpot'])
            if p['pose']['sourceCacheRebind']:
                sources=[row for row in actual['metadata']['effective'] if row['name']=='Source Library']
                if len(sources)!=1 or sources[0]['value'].replace('\\','/').casefold()!=(d/'design.dsn').as_posix().casefold():raise CadenceError('net_symbol_source_rebind_mismatch','Recreated symbol must bind exactly the owned output design cache.','verify')
                sources[0]['value']='__OWNED_OUTPUT_CACHE__'
            if actual['metadata']!=p['expectedSymbolMetadata']:raise CadenceError('net_symbol_metadata_mismatch','Symbol effective/user/display/font metadata differs from the frozen pose expectation.','verify')
            if sha256(d/'design.dsn')!=before:raise CadenceError('target_changed','Symbol metadata read changed output.')
            result.update(nativeSymbolRecreated=p['pose']['recreate'],nativeSymbolId=actual['nativeId'],symbolMetadataExpectedStateVerified=True,sourceCacheReboundToOutput=p['pose']['sourceCacheRebind'])
            result['notChecked'].append('unmodeled_symbol_extensions')
        return result
