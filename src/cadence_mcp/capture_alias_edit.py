"""Standalone scalar alias edits preserving native page pin/wire memberships."""
import copy,json,re
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_part_edit import page_geometry
from .capture_wire import inventory,connection_digest,point,point_on_path
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,run_tcl
from .page_net_partition import page_partition
from .isolated_jobs import digest

def definition_structure(data):
    rows=copy.deepcopy(data)
    for p in rows['pin']:p['net']=''
    return definition_baseline(rows)

def native_partition(capture,sid):
    session=capture._session(sid);directory=capture._workspace(session['workspaceId'])['directory'];out=directory/(new_id('page-partition')+'.json')
    run_tcl(capture.config,'inspect_page_net_partition.tcl',[str(session['design']),str(out)],directory);capture._session(sid)
    if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Native page net evidence exceeds limit.')
    rows=json.loads(out.read_text(encoding='utf-8'));page_partition(rows);out.unlink();return rows

def alias_changes(objects,target,operation,name,location):
    if operation not in ('set','delete'):raise CadenceError('invalid_alias_edit','Use set or delete.')
    old=target['attributes'];wire=next(o for o in objects if o['objectId']==old['wireId'] and o['kind']=='wire')
    if operation=='delete':
        if name is not None or location is not None:raise CadenceError('invalid_alias_edit','Deletion has no new name or location.')
    else:
        name=old['name'] if name is None else name;location=old['location'] if location is None else location
        if not isinstance(name,str) or not re.fullmatch(r'[^\s\[\]\x00-\x1f\x7f]{1,128}',name):raise CadenceError('invalid_alias_name','Use a bounded scalar net identifier without whitespace or bus brackets.')
        if not point(location) or not point_on_path(location,wire['attributes']['points']):raise CadenceError('invalid_alias_location','Alias anchor must lie on its existing owning wire.')
        if (name,location)==(old['name'],old['location']):raise CadenceError('no_change','Alias name and location already match.')
    same=[o for o in objects if o['kind']=='alias' and o['attributes']['wireId']==old['wireId'] and o['attributes']['name']==old['name'] and o['attributes']['location']==old['location']]
    if len(same)!=1:raise CadenceError('ambiguous_alias','Source alias semantic identity is not unique.')
    if operation=='set' and any(o['kind']=='alias' and o['objectId']!=target['objectId'] and o['attributes']['wireId']==old['wireId'] and (o['attributes']['name'],o['attributes']['location'])==(name,location) for o in objects):raise CadenceError('ambiguous_alias','New alias identity conflicts with another attached alias.')
    changed=copy.deepcopy(objects)
    if operation=='delete':changed=[o for o in changed if o['objectId']!=target['objectId']]
    else:
        for o in changed:
            if o['objectId']==target['objectId']:o['attributes'].update(name=name,location=location)
    return wire,changed,name,location

class CaptureAliasEdits(CapturePropertyEdits):
    kind='capture_alias_edit'
    def plan(self,sid,alias_id,operation,name=None,location=None,expected_wire_net=None):
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];objects=inventory(self.capture,sid);alias=next((o for o in objects if o['kind']=='alias' and o['objectId']==alias_id),None)
            if alias is None:raise CadenceError('object_not_found','Alias is outside this immutable session.')
            wire,changed,name,location=alias_changes(objects,alias,operation,name,location);page=next(p for p in data['page'] if p['objectId']==alias['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity is not unique.')
            if not 2<=len(wire['attributes']['points'])<=256:raise CadenceError('wire_shape_limit','Alias owner path exceeds supported bounds.')
            if operation=='set' and any(o['kind']=='wire' and o['pageId']==page['objectId'] and o['objectId']!=wire['objectId'] and o['attributes']['net']==name and name!=wire['attributes']['net'] for o in objects):raise CadenceError('alias_merge_unsupported','Cross-network alias merge requires its explicit connectivity operation.')
            owner=expected_wire_net if expected_wire_net is not None else (wire['attributes']['net'] if name==alias['attributes']['name'] else name) if operation=='set' else None
            if owner is not None and (not isinstance(owner,str) or not 1<=len(owner)<=512 or re.search(r'[\x00-\x1f\x7f]',owner)):raise CadenceError('invalid_net_name','Invalid explicit saved wire net expectation.')
            key=[sch['name'],page['name'],wire['nativeId']];rows=native_partition(self.capture,sid)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'aliasId':alias_id,'schematicName':sch['name'],'pageName':page['name'],'wireNativeId':wire['nativeId'],'oldPoints':wire['attributes']['points'],'oldNet':wire['attributes']['net'],'aliasName':alias['attributes']['name'],'oldLocation':alias['attributes']['location'],'operation':operation,'name':name or '','location':location or alias['attributes']['location'],'expectedWireNet':owner,'partitionDigest':digest(page_partition(rows,key,wire['attributes']['net'])),'expectedDefinitionDigest':definition_structure(data),'connectionDigest':connection_digest(data,changed),'expectedGeometry':page_geometry(self.capture,sid,page['objectId'])}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Alias plan exceeds durable bounds.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('aliasId','schematicName','pageName','aliasName','oldLocation','operation','name','location','expectedWireNet','sourceFingerprint')}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Alias source changed after planning.')
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);write_json(d/'alias-edit.json',{k:p[k] for k in ('schematicName','pageName','wireNativeId','oldPoints','oldNet','aliasName','oldLocation','operation','name','location')});return super().execute(d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_alias.tcl',self.config.install_root,d/'design.dsn',d/'alias-edit.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        target=checked_path(str(d/'design.dsn'),(d,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Alias output exceeds limit.')
        if native_completed:
            receipt=d/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':p['operation']}:raise CadenceError('invalid_worker_result','Alias save receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':d,'manifest':{'copiedFingerprint':before}};sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data'];objs=inventory(verifier,sid)
            if definition_structure(data)!=p['expectedDefinitionDigest'] or connection_digest(data,objs)!=p['connectionDigest']:raise CadenceError('alias_objects_mismatch','Saved definitions or alias/connection object semantics differ.','verify')
            names={s['objectId']:s['name'] for s in data['schematic']};pages=[pg for pg in data['page'] if pg['name']==p['pageName'] and names[pg['schematicId']]==p['schematicName']]
            if len(pages)!=1 or page_geometry(verifier,sid,pages[0]['objectId'])!=p['expectedGeometry']:raise CadenceError('alias_geometry_mismatch','Alias edit changed part poses or hotspots.','verify')
            rows=native_partition(verifier,sid);key=[p['schematicName'],p['pageName'],p['wireNativeId']]
            if digest(page_partition(rows,key,p['expectedWireNet']))!=p['partitionDigest']:raise CadenceError('alias_partition_mismatch','Native page pin/wire membership or unrelated net names changed.','verify')
            observed=next(r['netName'] for r in rows if r['kind']=='wire' and [r['schematicName'],r['pageName'],r['nativeId']]==key)
        finally:verifier.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Alias output changed during verification.')
        ident=d.name.removeprefix('plan-');artifact={'artifactId':'alias-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'sourceModified':False,'scope':'scalar_alias_preserve_page_net_membership','observedWireNet':observed,'nativePagePartitionsVerified':True,'designPassed':None,'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),'notChecked':['occurrence_flat_nets','cross_page_global_connectivity','intentional_network_merges','bus_aliases','alias_font_rotation','other_page_geometry','other_part_properties','rendering','native_drc']}
