"""Unit-aware implementation branch of existing part edit tasks."""
import copy,json
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import definition_baseline
from .capture_geometry import read_part_geometry
from .capture_part_edit import declared_pose,geometry_row
from .capture_properties import read_part_properties
from .capture_references import read_units
from .capture_multiunit_place import existing_definitions
from .capture_cache import query_cache
from .capture_wire import inventory,connection_digest
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS,run_tcl
from .isolated_jobs import digest

IDENTITY=('nativeId','schematicName','pageName','reference','kind','isExternalDesignPart','packageName','packageSize','deviceDesignator','referenceDesignator')
def identities_digest(rows,deleted=None):
 return digest(sorted(([r[k] for k in IDENTITY] for r in rows.values() if r['nativeId']!=deleted),key=lambda q:json.dumps(q)))

def cache_digest(capture,sid):
 query_cache(capture,sid,'package',limit=1000)
 return cache_graph_digest(capture.sessions[sid]['cacheDefinitions'])

def cache_graph_digest(data):
 pk={p['objectId']:p['name'] for p in data['package']};dv={d['objectId']:[pk[d['packageId']],d['designator'],d['position']] for d in data['device']};cells={c['objectId']:c['name'] for c in data['cell']};parts={p['objectId']:[*dv[p['deviceId']],cells[p['cellId']],p['name']] for p in data['part']}
 return digest({'package':sorted([[p[k] for k in ('name','size','homogeneous','footprint')] for p in data['package']]),'device':sorted([*dv[d['objectId']],cells[d['cellId']]] for d in data['device']),'part':sorted(parts.values()),'pin':sorted([*parts[p['partId']],p['position'],p['number'],p['name'],p['pinType'],p['visible'],p['shared'],p['swapId'],p['hotSpot']] for p in data['pin'])})

def critical_properties(capture,sid,part):
 props={p['name']:p['value'] for p in read_part_properties(capture,sid,part)['items']}
 return {k:props.get(k) for k in ('Value','PCB Footprint')}

def validate_physical_bindings(data,units):
 physical={}
 for pin in data['pin']:
  unit=units[pin['partId']]
  if unit['kind']!='placed' or unit['packageSize']<2 or not pin['number']:continue
  key=(unit['schematicName'],unit['reference'].casefold(),unit['packageName'],pin['number']);binding=(pin['connected'],pin['net'].casefold() if pin['connected'] else None)
  if key in physical and physical[key]!=binding:raise CadenceError('shared_pin_binding_conflict','Contradictory physical-pad expectations require resolved local/flat shared-pin semantics.')
  physical[key]=binding

def plan_unit_edit(writer,sid,part_id,operation,legacy,location,rotation,mirror,pins,expectations):
 if legacy:raise CadenceError('invalid_expectations','Choose either legacy reference expectations or unit pinId expectations.')
 if operation not in ('set_pose','delete'):raise CadenceError('invalid_part_edit','Use set_pose or delete.')
 if operation=='delete' and (any(v is not None for v in (location,rotation,mirror)) or pins not in (None,[])):raise CadenceError('invalid_part_edit','Deletion has no new pose or target pins.')
 with writer.capture.lock:
  capture=writer.capture;session=capture._session(sid);data=session['data'];part=next((p for p in data['part'] if p['objectId']==part_id),None)
  if part is None:raise CadenceError('object_not_found','Target unit is outside this immutable session.')
  units=read_units(capture,sid);unit=units[part_id]
  if unit['kind']!='placed' or unit['isExternalDesignPart'] or unit['packageSize']<2:raise CadenceError('unsupported_unit_scope','This branch edits one internal placed multiunit definition.')
  page=next(p for p in data['page'] if p['objectId']==part['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
  if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity is not unique.')
  objects=inventory(capture,sid)
  if any(o['kind']=='nc' and o['attributes'].get('partId')==part_id for o in objects):raise CadenceError('attached_nc_unsupported','Attached NC lifecycle needs explicit separate handling.')
  old=geometry_row(read_part_geometry(capture,sid,part_id));new=None if operation=='delete' else declared_pose(old,location,rotation,mirror,pins)
  expected=copy.deepcopy(data)
  if operation=='delete':expected['part']=[p for p in expected['part'] if p['objectId']!=part_id];expected['pin']=[p for p in expected['pin'] if p['partId']!=part_id]
  expected=existing_definitions(expected,page['objectId'],expectations);validate_physical_bindings(expected,units);remaining=[p for p in data['part'] if p['pageId']==page['objectId'] and not (operation=='delete' and p['objectId']==part_id)]
  if len(remaining)>100:raise CadenceError('input_limit','Bound complete-page geometry to 100 remaining instances.')
  geometry=[]
  for p in remaining:geometry.append({'nativeId':units[p['objectId']]['nativeId'],'geometry':new if p['objectId']==part_id else geometry_row(read_part_geometry(capture,sid,p['objectId'])),'properties':critical_properties(capture,sid,p['objectId'])})
  netpins=[{'reference':units[p['partId']]['referenceDesignator'] or units[p['partId']]['reference'],'number':p['number'],'name':p['name'],'connected':p['connected'],'net':p['net']} for p in expected['pin'] if p['pageId']==page['objectId']]
  payload={'unitAware':True,'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'partId':part_id,'unit':{k:unit[k] for k in IDENTITY},'schematicName':sch['name'],'pageName':page['name'],'operation':operation,'oldGeometry':old,'newGeometry':new,'expectedPageGeometry':geometry,'expectedNativePins':netpins,'expectedDefinitionDigest':definition_baseline(expected),'connectionDigest':connection_digest(data,objects),'identityDigest':identities_digest(units,unit['nativeId'] if operation=='delete' else None),'cacheDigest':cache_digest(capture,sid)}
  if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>160000:raise CadenceError('plan_limit','Unit edit snapshot exceeds its bounded durable record.')
  capture._session(sid);return writer.create_plan(payload)

def unit_command(writer,directory,p):
 with (directory/'unit-request.json').open('x',encoding='utf-8') as f:json.dump(p,f,ensure_ascii=False,separators=(',',':'))
 return [writer.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_unit_part.tcl',writer.config.install_root,directory/'design.dsn',directory/'unit-request.json',directory/'native-result.json']

def verification_error(code,message):return CadenceError(code,message,'verify')

def verify_unit_edit(writer,directory,p,native_completed):
 target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
 if target.stat().st_size>128*1024*1024:raise verification_error('output_limit','Unit edit output exceeds design size bound.')
 if native_completed:
  receipt=directory/'native-result.json'
  if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':p['operation'],'nativeId':p['unit']['nativeId']}:raise verification_error('invalid_worker_result','Unit edit save receipt mismatch.')
 verifier=CaptureService(writer.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}};sid=verifier.open('output')['sessionId']
 try:
  data=verifier.sessions[sid]['data']
  if definition_baseline(data)!=p['expectedDefinitionDigest']:raise verification_error('unit_edit_net_mismatch','Saved pin definitions/nets differ from the complete unit-aware expectation.')
  if connection_digest(data,inventory(verifier,sid))!=p['connectionDigest']:raise verification_error('unit_edit_connection_objects_changed','Wires, aliases or other connection objects changed.')
  units=read_units(verifier,sid)
  if identities_digest(units)!=p['identityDigest']:raise verification_error('unit_edit_identity_mismatch','An unplanned unit ownership or full reference changed.')
  for row in p['expectedPageGeometry']:
   selected=[u for u in units.values() if u['nativeId']==row['nativeId'] and u['schematicName']==p['schematicName'] and u['pageName']==p['pageName']]
   if len(selected)!=1 or geometry_row(read_part_geometry(verifier,sid,selected[0]['partId']))!=row['geometry']:raise verification_error('unit_edit_geometry_mismatch','Target or another page instance differs from declared pose/hotspots.')
   if critical_properties(verifier,sid,selected[0]['partId'])!=row['properties']:raise verification_error('unit_edit_properties_changed','A remaining unit lost its Value/PCB Footprint.')
  if cache_digest(verifier,sid)!=p['cacheDigest']:raise verification_error('unit_edit_cache_changed','Cached package/device/part/pin mapping metadata changed.')
  out=directory/'unit-native-bindings.json'
  if out.exists():out.unlink()
  run_tcl(writer.config,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],directory);bindings=json.loads(out.read_text(encoding='utf-8'));groups={}
  for pin in p['expectedNativePins']:
   rows=[b for b in bindings if b['kind']=='pin' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and all(b[k]==pin[k] for k in ('reference','number','name'))]
   if len(rows)!=1 or (rows[0]['group'] is not None)!=pin['connected'] or rows[0]['netName']!=pin['net']:raise verification_error('unit_edit_native_binding_mismatch','A remaining pin differs from its native network expectation.')
   if pin['connected']:groups.setdefault(pin['net'],set()).add(rows[0]['group'])
  for name,group in groups.items():
   group.update(b['group'] for b in bindings if b['kind']=='wire' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and b['netName']==name)
   if len(group)!=1 or None in group:raise verification_error('unit_edit_native_partition_mismatch','Declared pin/wire members differ from native network objects.')
  if len({next(iter(g)) for g in groups.values()})!=len(groups):raise verification_error('unit_edit_native_partition_mismatch','Distinct declared nets unexpectedly merge.')
 finally:verifier.close(sid)
 writer.preflight(p)
 if sha256(target)!=before:raise verification_error('target_changed','Unit output changed during verification.')
 ident=directory.name.removeprefix('plan-');artifact={'artifactId':'unit-edit-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
 return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'operation':p['operation'],'unitAware':True,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'unitIdentityVerified':True,'pageGeometryVerified':True,'expectedDefinitionsVerified':True,'nativePageNetworksVerified':True,'cachePinMetadataVerified':True,'valueFootprintPreserved':True,'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(writer.config.workspace_root).as_posix(),'notChecked':['incremental_unit_add','cross_page_unit_assignment','full_graphic_cache_identity','flat_occurrence_connectivity','attached_nc_lifecycle','native_drc','rendered_layout']}
