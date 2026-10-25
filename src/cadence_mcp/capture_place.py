"""Library-bound placement with caller-declared pin hotspots and net expectations."""
from collections import Counter
from datetime import datetime,timezone
import copy,json,re,shutil,uuid
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_geometry import read_part_geometry
from .capture_properties import read_part_properties
from .capture_wire import point,expected_definitions,inventory,connection_digest,geometry_union,paths_valid
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS,process_env,run_tcl
from .process_tree import run_owned_process
from .embedded_tcl import command as embedded_command


def validate_pins(source,pins):
    if not isinstance(pins,list) or not 1<=len(pins)<=500:raise CadenceError('invalid_expected_pins','Declare every new physical pin and global hotspot.')
    for pin in pins:
        if not isinstance(pin,dict) or set(pin)!={'number','name','hotSpot','connected','net'} or not isinstance(pin['number'],str) or not isinstance(pin['name'],str) or not point(pin['hotSpot']) or type(pin['connected']) is not bool:
            raise CadenceError('invalid_expected_pins','Invalid expected pin shape.')
        if pin['connected']:
            if not isinstance(pin['net'],str) or not pin['net'] or len(pin['net'])>512:raise CadenceError('invalid_expected_pins','Connected new pins need explicit native net names.')
        elif pin['net'] is not None:raise CadenceError('invalid_expected_pins','Unbound new pins require null net.')
    expected=Counter((p['number'],p['name']) for p in pins)
    if expected!=Counter((p['number'],p['name']) for p in source) or any(n!=1 for n in expected.values()):
        raise CadenceError('pin_mapping_mismatch','New pin declarations must exactly match the selected library part/device physical mapping without ambiguous duplicates.')


class CapturePlacements(CapturePropertyEdits):
    kind='capture_placement'
    def __init__(self,config,capture,library):super().__init__(config,capture);self.library=library

    def plan(self,sid,page_id,library_id,part_id,reference,location,rotation,mirror,value,pins,existing_connections,expected_paths=None):
        if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}',reference):raise CadenceError('invalid_reference','Provide an explicit bounded new reference.')
        if not point(location) or type(rotation) is not int or rotation not in range(4) or type(mirror) is not int or mirror not in (0,1):raise CadenceError('invalid_placement','Invalid location or raw rotation/mirror code.')
        if not isinstance(value,str) or len(value)>1024 or '\x00' in value:raise CadenceError('invalid_value','Invalid explicit part value.')
        with self.capture.lock,self.library.lock:
            session=self.capture._session(sid);data=session['data'];lib=self.library._session(library_id);ld=lib['data']
            page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('object_not_found','Page is outside the design session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            if any(p['reference'].casefold()==reference.casefold() for p in data['part']):raise CadenceError('reference_conflict','Existing references and additional shared units require a dedicated package-aware operation.')
            part=next((p for p in ld['part'] if p['objectId']==part_id),None)
            if part is None:raise CadenceError('object_not_found','Part is outside the library session.')
            device=next(d for d in ld['device'] if d['objectId']==part['deviceId']);cell=next(c for c in ld['cell'] if c['objectId']==part['cellId']);package=next(p for p in ld['package'] if p['objectId']==part['packageId'])
            source_pins=[p for p in ld['pin'] if p['partId']==part_id];validate_pins(source_pins,pins)
            expected=expected_definitions(data,page_id,existing_connections)
            new_id='planned-new-part'
            expected['part'].append({'objectId':new_id,'pageId':page_id,'schematicId':page['schematicId'],'reference':reference})
            for i,pin in enumerate(pins):expected['pin'].append({'objectId':f'planned-pin-{i}','partId':new_id,'pageId':page_id,'schematicId':page['schematicId'],'reference':reference,'number':pin['number'],'name':pin['name'],'connected':pin['connected'],'net':pin['net'] or ''})
            objects=inventory(self.capture,sid);expected_objects=objects
            if expected_paths is not None:
                prior=[o['attributes']['points'] for o in objects if o['kind']=='wire' and o['pageId']==page_id]
                if not paths_valid(expected_paths) or geometry_union(expected_paths)!=geometry_union(prior):raise CadenceError('invalid_wire_geometry','Placement must preserve existing wire geometric union.')
                expected_objects=[o for o in objects if not (o['kind']=='wire' and o['pageId']==page_id)]+[{'kind':'wire','pageId':page_id,'attributes':{'points':p}} for p in expected_paths]
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],
                'sourceLibrary':str(lib['directory']/'library.olb'),'libraryFingerprint':lib['revision'],
                'schematicName':sch['name'],'pageName':page['name'],'packageName':package['name'],'deviceDesignator':device['designator'],
                'devicePosition':device['position'],'cellName':cell['name'],'partName':part['name'],
                'sourceCellPartCount':sum(p['cellId']==part['cellId'] for p in ld['part']),
                'cacheName':'MCP_'+uuid.uuid4().hex[:20],'reference':reference,'location':location,'rotation':rotation,'mirror':mirror,
                'value':value,'expectedFootprint':package['footprint'],'expectedPins':pins,'existingConnections':existing_connections,
                'expectedDefinitionDigest':definition_baseline(expected),'expectedConnectionDigest':connection_digest(data,expected_objects)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Placement plan exceeds bounded durable-record size.')
            self.capture._session(sid);self.library._session(library_id)
            return self.create_plan(payload)

    def preview(self,p):return {k:p[k] for k in ('schematicName','pageName','packageName','deviceDesignator','cellName','partName','cacheName','reference','location','rotation','mirror','value','expectedPins','existingConnections','sourceFingerprint','libraryFingerprint')}

    def preflight(self,p):
        for path,key in [('sourceDesign','sourceFingerprint'),('sourceLibrary','libraryFingerprint')]:
            source=checked_path(p[path],(self.config.workspace_root,))
            if not source.is_file() or sha256(source)!=p[key]:raise CadenceError('target_changed','Design or library snapshot changed after placement planning.')

    def execute(self,directory,p,cancel,on_started):
        self.preflight(p)
        for key,name,fp in [('sourceDesign','design.dsn','sourceFingerprint'),('sourceLibrary','library.olb','libraryFingerprint')]:
            source=checked_path(p[key],(self.config.workspace_root,))
            with source.open('rb') as original,(directory/name).open('xb') as target:shutil.copyfileobj(original,target)
            if sha256(directory/name)!=p[fp] or sha256(source)!=p[fp]:raise CadenceError('target_changed','Input changed during placement copy.')
        args=[self.config.install_root,directory/'design.dsn',directory/'library.olb',directory/'native-result.json',
              p['schematicName'],p['pageName'],p['packageName'],p['deviceDesignator'],str(p['devicePosition']),p['cellName'],p['partName'],str(p['sourceCellPartCount']),p['cacheName'],p['reference'],*map(str,p['location']),str(p['rotation']),str(p['mirror']),p['value']]
        return run_owned_process(embedded_command(self.config.install_root,'edit_place.tcl',args[1:]),directory,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)

    def verify(self,directory,p,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Placed output exceeds design limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'reference':p['reference'],'cacheName':p['cacheName']}:raise CadenceError('invalid_worker_result','Placement save receipt mismatch.','verify')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('placement_definition_mismatch','Saved part/pin mappings or net bindings differ from the explicit placement plan.','verify')
            if connection_digest(data,inventory(verifier,sid))!=p['expectedConnectionDigest']:raise CadenceError('placement_connection_objects_changed','Saved connection objects differ from planned preservation.','verify')
            candidates=[r for r in data['part'] if r['reference']==p['reference']]
            if len(candidates)!=1:raise CadenceError('ambiguous_target','Placed reference is not unique after save.')
            part=candidates[0];geometry=read_part_geometry(verifier,sid,part['objectId'])
            if (geometry['location'],geometry['rotationCode'],geometry['mirrorCode'])!=(p['location'],p['rotation'],p['mirror']):raise CadenceError('placement_pose_mismatch','Saved placement pose differs from plan.','verify')
            if sorted((q['number'],q['name'],q['hotSpot']) for q in geometry['pins'])!=sorted((q['number'],q['name'],q['hotSpot']) for q in p['expectedPins']):raise CadenceError('placement_hotspot_mismatch','Actual native global hotspots differ from caller expectations.','verify')
            props={r['name']:r['value'] for r in read_part_properties(verifier,sid,part['objectId'])['items']}
            if props.get('Value')!=p['value'] or props.get('PCB Footprint')!=p['expectedFootprint']:raise CadenceError('placement_property_mismatch','Placed value or inherited footprint differs from plan.','verify')
        finally:verifier.close(sid)
        if sha256(target)!=before:raise CadenceError('target_changed','Placed output changed during verification.')
        if p['sourceCellPartCount']>1:
            # Fixed read-only native comparison in a fresh process, including line geometry.
            if sha256(directory/'library.olb')!=p['libraryFingerprint']:raise CadenceError('target_changed','Private source library changed before view verification.')
            view_result=directory/'verified-view.json'
            if view_result.exists():view_result.unlink()
            run_tcl(self.config,'inspect_placed_view.tcl',[str(target),str(directory/'library.olb'),str(view_result),p['schematicName'],p['pageName'],p['reference'],p['packageName'],p['deviceDesignator'],p['partName']],directory)
            view=json.loads(view_result.read_text(encoding='utf-8'))
            if view.get('matches') is not True:raise CadenceError('placement_view_mismatch','Saved instance does not retain the selected source pin/line view.','verify')
            if sha256(target)!=before or sha256(directory/'library.olb')!=p['libraryFingerprint']:raise CadenceError('target_changed','Placed output or private source library changed during view verification.')
        self.preflight(p);ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'placed-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedDefinitionsVerified':True,'expectedGlobalHotspotsVerified':True,'sourceModified':False,'libraryModified':False,'sourcePinLineViewVerified':p['sourceCellPartCount']>1,'sourceVectorGeometryVerified':p['sourceCellPartCount']>1,'embeddedCacheClosureVerified':False,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['embedded_cache_closure','shared_package_unit_lifecycle','occurrence_connectivity','native_drc','rendered_layout','pin_electrical_types']}

