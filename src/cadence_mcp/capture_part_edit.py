"""Fixed definition-level part pose/deletion, explicit pin and hotspot oracles."""
import copy,json
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_geometry import read_part_geometry
from .capture_wire import point,inventory,connection_digest,expected_definitions
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS

def geometry_row(row):
    return {'location':row['location'],'rotationCode':row['rotationCode'],'mirrorCode':row['mirrorCode'],
            'pins':sorted([{k:p[k] for k in ('number','name','hotSpot')} for p in row['pins']],key=lambda p:(p['number'],p['name']))}

def page_geometry(capture,sid,page_id):
    session=capture._session(sid)
    parts=[p for p in session['data']['part'] if p['pageId']==page_id]
    if len(parts)>100:raise CadenceError('input_limit','Part edit currently bounds the page geometry baseline to 100 parts.')
    if len({p['reference'] for p in parts})!=len(parts):raise CadenceError('ambiguous_target','Repeated page references require a unit-aware editor.')
    return {p['reference']:geometry_row(read_part_geometry(capture,sid,p['objectId'])) for p in parts}

def declared_pose(old,location,rotation,mirror,pins):
    if not point(location) or type(rotation) is not int or rotation not in range(4) or type(mirror) is not int or mirror not in (0,1):
        raise CadenceError('invalid_pose','Provide bounded integer location, rotation 0..3 and mirror 0..1.')
    if not isinstance(pins,list) or len(pins)>500:raise CadenceError('invalid_hotspots','Provide the complete explicit target pin hotspot table.')
    seen=set()
    for pin in pins:
        if not isinstance(pin,dict) or set(pin)!={'number','name','hotSpot'} or any(not isinstance(pin[k],str) or len(pin[k])>512 or '\x00' in pin[k] for k in ('number','name')) or not point(pin['hotSpot']):
            raise CadenceError('invalid_hotspots','Invalid explicit target pin hotspot.')
        identity=(pin['number'],pin['name'])
        if identity in seen:raise CadenceError('invalid_hotspots','Duplicate target pin identity.')
        seen.add(identity)
    if seen!={(p['number'],p['name']) for p in old['pins']} or len(pins)!=len(old['pins']):raise CadenceError('incomplete_hotspots','Every target pin must be declared exactly once.')
    return {'location':location,'rotationCode':rotation,'mirrorCode':mirror,'pins':sorted(copy.deepcopy(pins),key=lambda p:(p['number'],p['name']))}

class CapturePartEdits(CapturePropertyEdits):
    kind='capture_part_edit'
    max_record_bytes=262144
    def plan(self,sid,part_id,operation,expectations,location=None,rotation=None,mirror=None,expected_pins=None,unit_expectations=None):
        if unit_expectations is not None:
            from .capture_unit_edit import plan_unit_edit
            return plan_unit_edit(self,sid,part_id,operation,expectations,location,rotation,mirror,expected_pins,unit_expectations)
        if operation not in ('set_pose','delete'):raise CadenceError('invalid_part_edit','Use set_pose or delete.')
        if operation=='delete' and (any(v is not None for v in (location,rotation,mirror)) or expected_pins not in (None,[])):
            raise CadenceError('invalid_part_edit','Deletion has no new pose or target pins.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data']
            part=next((p for p in data['part'] if p['objectId']==part_id),None)
            if part is None:raise CadenceError('object_not_found','Target part is outside this session.')
            page=next(p for p in data['page'] if p['objectId']==part['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:
                raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            if any(len(s)>512 or '\x00' in s for s in (sch['name'],page['name'],part['reference'])):raise CadenceError('input_limit','Target locator exceeds literal bounds.')
            geometry=page_geometry(self.capture,sid,page['objectId']);old=geometry[part['reference']]
            objects=inventory(self.capture,sid)
            if any(o['kind']=='nc' and o['attributes'].get('partId')==part_id for o in objects):raise CadenceError('attached_nc_unsupported','Target-attached NC markers need an explicit lifecycle operation.')
            expected_data=copy.deepcopy(data)
            if operation=='delete':
                expected_data['part']=[p for p in expected_data['part'] if p['objectId']!=part_id]
                expected_data['pin']=[p for p in expected_data['pin'] if p['partId']!=part_id]
                del geometry[part['reference']]
            else:geometry[part['reference']]=declared_pose(old,location,rotation,mirror,expected_pins)
            expected_data=expected_definitions(expected_data,page['objectId'],expectations)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'partId':part_id,
                     'schematicName':sch['name'],'pageName':page['name'],'reference':part['reference'],'operation':operation,
                     'oldPose':{k:old[k] for k in ('location','rotationCode','mirrorCode')},
                     'newPose':None if operation=='delete' else {k:geometry[part['reference']][k] for k in ('location','rotationCode','mirrorCode')},
                     'expectedGeometry':geometry,'expectedConnections':expectations,
                     'expectedDefinitionDigest':definition_baseline(expected_data),'connectionDigest':connection_digest(data,objects)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Part edit baseline exceeds durable plan bounds.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):
        if p.get('unitAware'):return {k:p[k] for k in ('unitAware','unit','operation','schematicName','pageName','oldGeometry','newGeometry','expectedNativePins','sourceFingerprint')}
        return {k:p[k] for k in ('operation','partId','schematicName','pageName','reference','oldPose','newPose','expectedGeometry','expectedConnections','sourceFingerprint')}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Part edit source changed after planning.')
    def native_command(self,directory,p):
        if p.get('unitAware'):
            from .capture_unit_edit import unit_command
            return unit_command(self,directory,p)
        old=p['oldPose'];new=p['newPose'] or old
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_part.tcl',self.config.install_root,directory/'design.dsn',directory/'native-result.json',p['schematicName'],p['pageName'],p['reference'],p['operation'],*map(str,old['location']),str(old['rotationCode']),str(old['mirrorCode']),*map(str,new['location']),str(new['rotationCode']),str(new['mirrorCode'])]
    def verify(self,directory,p,native_completed):
        if p.get('unitAware'):
            from .capture_unit_edit import verify_unit_edit
            return verify_unit_edit(self,directory,p,native_completed)
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Part edit output exceeds limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':p['operation']}:raise CadenceError('invalid_worker_result','Part edit save receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('part_edit_net_mismatch','Saved definitions/pin bindings differ from explicit expectations.','verify')
            if connection_digest(data,inventory(verifier,sid))!=p['connectionDigest']:raise CadenceError('part_edit_connection_objects_changed','Saved wires/aliases/other connection objects changed.','verify')
            names={s['objectId']:s['name'] for s in data['schematic']}
            pages=[pg for pg in data['page'] if pg['name']==p['pageName'] and names[pg['schematicId']]==p['schematicName']]
            if len(pages)!=1 or page_geometry(verifier,sid,pages[0]['objectId'])!=p['expectedGeometry']:raise CadenceError('part_edit_geometry_mismatch','Saved page poses and global hotspots differ from explicit expectations.','verify')
        finally:verifier.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Part edit output changed during verification.')
        ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'part-edit-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','operation':p['operation'],'artifact':artifact,
                'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedDefinitionsVerified':True,'pageGeometryVerified':True,
                'sourceModified':False,'designPassed':None,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['occurrence_connectivity','shared_package_unit_lifecycle','attached_nc_lifecycle','rendered_text','other_page_geometry','other_part_properties','native_drc']}
