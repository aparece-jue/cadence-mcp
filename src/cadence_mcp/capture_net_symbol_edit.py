"""Scalar attached global/offpage name/delete with native page partitions."""
import copy,json,re
from .capture_alias_edit import CaptureAliasEdits,definition_structure
from .capture_part_edit import page_geometry
from .capture_wire import inventory,connection_digest,point_on_path
from .page_net_partition import page_partition
from .isolated_jobs import digest
from .core import CadenceError,new_id,write_json,sha256
from .environment import ADAPTERS,run_tcl

def binding_rows(capture,sid):
    s=capture._session(sid);d=capture._workspace(s['workspaceId'])['directory'];out=d/(new_id('symbol-bindings')+'.json')
    run_tcl(capture.config,'inspect_net_symbol_bindings.tcl',[str(s['design']),str(out)],d);capture._session(sid)
    if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Symbol binding evidence exceeds limit.')
    rows=json.loads(out.read_text(encoding='utf-8'));page_partition([r for r in rows if r['kind'] in ('pin','wire')]);out.unlink();return rows

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

class CaptureNetSymbolEdits(CaptureAliasEdits):
    kind='capture_net_symbol_edit'
    def plan(self,sid,symbol_id,wire_id,operation,name=None,expected_wire_net=None):
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];objects=inventory(self.capture,sid)
            target=next((o for o in objects if o['objectId']==symbol_id and o['kind'] in ('global','offpage')),None)
            if target is None:raise CadenceError('object_not_found','Global/offpage target is outside this session.')
            changed=symbol_changes(objects,target,operation,name);old=target['attributes']
            page=next(p for p in data['page'] if p['objectId']==target['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page must be unique.')
            wire=next((o for o in objects if o['objectId']==wire_id and o['kind']=='wire' and o['pageId']==page['objectId']),None)
            if wire is None or not point_on_path(old['hotSpot'],wire['attributes']['points']):raise CadenceError('invalid_symbol_wire','Provide the existing target wire at the symbol hotspot.')
            if operation=='set_name' and symbol_name_conflicts(objects,symbol_id,wire_id,name):raise CadenceError('net_symbol_merge_unsupported','Name already exists in another connection object; explicit network merge is required.')
            rows=binding_rows(self.capture,sid);scope=(sch['name'],page['name']);key=[*scope,wire['nativeId']]
            symbols=[r for r in rows if r['kind']==target['kind'] and (r['schematicName'],r['pageName'])==scope and r['name']==old['name'] and r['hotSpot']==old['hotSpot']]
            wires=[r for r in rows if r['kind']=='wire' and [r['schematicName'],r['pageName'],r['nativeId']]==key]
            if len(symbols)!=1 or len(wires)!=1 or symbols[0]['group'] is None or symbols[0]['group']!=wires[0]['group']:raise CadenceError('net_symbol_binding_mismatch','Target symbol and declared wire must share one native page net.')
            owner=expected_wire_net if expected_wire_net is not None else name if operation=='set_name' else None
            if owner is not None and (not isinstance(owner,str) or not 1<=len(owner)<=512 or re.search(r'[\x00-\x1f\x7f]',owner)):raise CadenceError('invalid_net_name','Invalid explicit saved wire net expectation.')
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'symbolId':symbol_id,'wireId':wire_id,'kind':target['kind'],'nativeId':target['nativeId'],'schematicName':scope[0],'pageName':scope[1],'oldName':old['name'],'oldLocation':old['location'],'oldHotSpot':old['hotSpot'],'oldRotation':old['rotationCode'],'oldMirror':old['mirrorCode'],'operation':operation,'name':name or '', 'wireNativeId':wire['nativeId'],'expectedWireNet':owner,'partitionDigest':digest(page_partition([r for r in rows if r['kind'] in ('pin','wire')],key)),'expectedDefinitionDigest':definition_structure(data),'connectionDigest':connection_digest(data,changed),'expectedGeometry':page_geometry(self.capture,sid,page['objectId'])}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Symbol plan exceeds durable limit.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('symbolId','wireId','kind','schematicName','pageName','oldName','oldLocation','oldHotSpot','operation','name','expectedWireNet','sourceFingerprint')}
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);write_json(d/'symbol-edit.json',{k:p[k] for k in ('kind','nativeId','schematicName','pageName','oldName','oldLocation','oldHotSpot','oldRotation','oldMirror','operation','name')})
        # Bypass the alias-specific request writer while retaining the owned copy/job implementation.
        from .capture_edit import CapturePropertyEdits
        return CapturePropertyEdits.execute(self,d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_net_symbol_name.tcl',self.config.install_root,d/'design.dsn',d/'symbol-edit.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        result=super().verify(d,p,native_completed)
        if p['operation']=='set_name':
            target=d/'design.dsn';out=d/(new_id('symbol-binding')+'.json');before=sha256(target)
            if before!=result['artifact']['sha256']:raise CadenceError('target_changed','Symbol output changed between verification stages.')
            run_tcl(self.config,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],d)
            if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Symbol binding evidence exceeds limit.')
            rows=json.loads(out.read_text(encoding='utf-8'));scope=(p['schematicName'],p['pageName'])
            symbols=[r for r in rows if r['kind']==p['kind'] and (r['schematicName'],r['pageName'])==scope and r['name']==p['name'] and r['hotSpot']==p['oldHotSpot']]
            wires=[r for r in rows if r['kind']=='wire' and (r['schematicName'],r['pageName'])==scope and r['nativeId']==p['wireNativeId']]
            if len(symbols)!=1 or len(wires)!=1 or symbols[0]['group'] is None or symbols[0]['group']!=wires[0]['group']:raise CadenceError('net_symbol_binding_mismatch','Renamed symbol lost its declared native wire binding.')
            if sha256(target)!=before:raise CadenceError('target_changed','Symbol binding read changed output.')
            self.preflight(p)
        result.update(scope='scalar_net_symbol_name_delete_preserve_page_membership',symbolKind=p['kind'],occurrenceConnectivityVerified=False)
        result['artifact']['artifactId']='net-symbol-edit-'+d.name.removeprefix('plan-')
        result['notChecked']=['symbol_pose_lifecycle','cross_page_global_offpage_flat_connectivity','occurrence_flat_nets','other_page_geometry','other_part_properties','rendering','native_drc']
        return result
