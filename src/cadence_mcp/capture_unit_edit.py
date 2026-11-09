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
from .capture_wire import inventory,connection_digest,path_key,point_on_path
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS,run_tcl
from .isolated_jobs import digest
from .page_net_partition import native_partition,page_partition

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

def prepare_wire_ends(capture,sid,data,objects,unit,page_id,part_id,old,new,requests):
 if not isinstance(requests,list) or not 1<=len(requests)<=32:
  raise CadenceError('invalid_unit_wire_ends','Declare between 1 and 32 terminal wire edits.')
 if any(not isinstance(row,dict) or set(row)!={'wireId','pinId'} or
        any(not isinstance(value,str) for value in row.values()) for row in requests):
  raise CadenceError('invalid_unit_wire_ends','Each terminal edit requires a wire ID and pin ID.')
 if any(len({row[key] for row in requests})!=len(requests) for key in ('wireId','pinId')):
  raise CadenceError('invalid_unit_wire_ends','Each wire and each pin may be edited only once.')
 wires={o['objectId']:o for o in objects if o['pageId']==page_id and o['kind']=='wire'}
 pins={p['objectId']:p for p in data['pin'] if p['partId']==part_id}
 old_points={(p['number'],p['name']):p['hotSpot'] for p in old['pins']}
 new_points={(p['number'],p['name']):p['hotSpot'] for p in new['pins']}
 scope=(unit['schematicName'],unit['pageName'])
 rows=native_partition(capture,sid)
 page_rows=[row for row in rows if (row['schematicName'],row['pageName'])==scope]
 revised=copy.deepcopy(objects)
 revised_by_id={o['objectId']:o for o in revised}
 moves=[]
 for request in requests:
  wire=wires.get(request['wireId'])
  pin=pins.get(request['pinId'])
  if wire is None or pin is None or not pin['connected']:
   raise CadenceError('invalid_unit_wire_ends','Use a same-page wire and a connected pin of the selected unit.')
  native_id=wire['nativeId']
  points=wire['attributes']['points']
  identity=(pin['number'],pin['name'])
  before=old_points.get(identity)
  after=new_points.get(identity)
  if before is None or after is None or len(points)!=2 or points.count(before)!=1 or before==after:
   raise CadenceError('unsupported_unit_wire_end','A moved hotspot must be an endpoint of a two-point terminal wire.')
  if any(other!=request['wireId'] and point_on_path(before,row['attributes']['points']) for other,row in wires.items()):
   raise CadenceError('unsupported_unit_wire_end','The old pin endpoint is also on another wire.')
  index=points.index(before)
  anchor=points[1-index]
  if before==anchor or (before[0]!=anchor[0] and before[1]!=anchor[1]):
   raise CadenceError('unsupported_unit_wire_end','The original terminal segment must be orthogonal and nonzero.')
  if after==anchor or (after[0]!=anchor[0] and after[1]!=anchor[1]):
   raise CadenceError('unsupported_unit_wire_end','The fixed endpoint and new hotspot must form one orthogonal segment.')
  replacement=copy.deepcopy(points)
  replacement[index]=after
  aliases=[o['attributes'] for o in objects if o['kind']=='alias' and o['attributes']['wireId']==request['wireId']]
  if any(not point_on_path(alias['location'],replacement) for alias in aliases):
   raise CadenceError('unsupported_unit_wire_end','The edited segment must retain every existing alias anchor.')
  if any(o['kind'] in ('global','offpage','port') and o['pageId']==page_id and
         point_on_path(o['attributes']['hotSpot'],points)!=point_on_path(o['attributes']['hotSpot'],replacement)
         for o in objects):
   raise CadenceError('unsupported_unit_wire_end','The edited segment cannot add or remove a net-symbol contact.')
  native_wires=[row for row in page_rows if row['kind']=='wire' and row['nativeId']==native_id]
  native_pins=[row for row in page_rows if row['kind']=='pin' and row['reference']==unit['referenceDesignator']
               and (row['number'],row['name'])==identity]
  if len(native_wires)!=1 or len(native_pins)!=1 or native_wires[0]['group'] is None or (
     native_wires[0]['group']!=native_pins[0]['group'] or native_wires[0]['netName']!=pin['net'] or
     native_wires[0]['points']!=points):
   raise CadenceError('unit_wire_binding_mismatch','The source native terminal wire and pin must share one net object.')
  native_wires[0]['points']=replacement
  revised_by_id[request['wireId']]['attributes']['points']=replacement
  moves.append({'wireId':request['wireId'],'pinId':request['pinId'],'nativeId':native_id,'oldPoints':points,
                'newPoints':replacement,'endpointIndex':index,'net':pin['net'],
                'aliases':sorted([a['name'],a['location']] for a in aliases)})
 return revised,moves,digest(page_partition(rows))

def plan_unit_edit(writer,sid,part_id,operation,legacy,location,rotation,mirror,pins,expectations,wire_ends=None):
 if legacy:raise CadenceError('invalid_expectations','Choose either legacy reference expectations or unit pinId expectations.')
 if wire_ends is not None and operation!='set_pose':
  raise CadenceError('invalid_unit_wire_ends','Terminal wire edits require a unit pose operation.')
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
  expected=existing_definitions(expected,page['objectId'],expectations)
  validate_physical_bindings(expected,units)
  expected_definition_digest=definition_baseline(expected)
  wire_metadata={}
  if wire_ends is not None:
   if definition_baseline(data)!=expected_definition_digest:
    raise CadenceError('invalid_unit_wire_ends','Terminal wire edits require every pin binding to remain unchanged.')
   objects,moves,partition=prepare_wire_ends(capture,sid,data,objects,unit,page['objectId'],part_id,old,new,wire_ends)
   wire_metadata={'wireEndMoves':moves,'expectedNativePartition':partition}
  remaining=[p for p in data['part'] if p['pageId']==page['objectId'] and not (operation=='delete' and p['objectId']==part_id)]
  if len(remaining)>100:raise CadenceError('input_limit','Bound complete-page geometry to 100 remaining instances.')
  geometry=[]
  for p in remaining:geometry.append({'nativeId':units[p['objectId']]['nativeId'],'geometry':new if p['objectId']==part_id else geometry_row(read_part_geometry(capture,sid,p['objectId'])),'properties':critical_properties(capture,sid,p['objectId'])})
  netpins=[{'reference':units[p['partId']]['referenceDesignator'] or units[p['partId']]['reference'],'number':p['number'],'name':p['name'],'connected':p['connected'],'net':p['net']} for p in expected['pin'] if p['pageId']==page['objectId']]
  payload={'unitAware':True,'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'partId':part_id,'unit':{k:unit[k] for k in IDENTITY},'schematicName':sch['name'],'pageName':page['name'],'operation':operation,'oldGeometry':old,'newGeometry':new,'expectedPageGeometry':geometry,'expectedNativePins':netpins,'expectedDefinitionDigest':expected_definition_digest,'connectionDigest':connection_digest(data,objects),'identityDigest':identities_digest(units,unit['nativeId'] if operation=='delete' else None),'cacheDigest':cache_digest(capture,sid),**wire_metadata}
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
  objects=inventory(verifier,sid)
  if connection_digest(data,objects)!=p['connectionDigest']:raise verification_error('unit_edit_connection_objects_changed','Wires, aliases or other connection objects changed.')
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
  if p.get('wireEndMoves'):
   schematics={s['objectId'] for s in data['schematic'] if s['name']==p['schematicName']}
   pages=[page['objectId'] for page in data['page'] if page['schematicId'] in schematics and page['name']==p['pageName']]
   if len(schematics)!=1 or len(pages)!=1:
    raise verification_error('unit_wire_identity_mismatch','The qualified terminal wire page is no longer unique.')
   selected_page_id=pages[0]
   partition=page_partition([row for row in bindings if row['kind'] in ('wire','pin')])
   if digest(partition)!=p['expectedNativePartition']:
    raise verification_error('unit_wire_partition_mismatch','Terminal edits changed native pin or wire membership.')
   for move in p['wireEndMoves']:
    wires=[obj for obj in objects if obj['kind']=='wire' and obj['pageId']==selected_page_id
           and obj['nativeId']==move['nativeId']]
    if len(wires)!=1 or path_key(wires[0]['attributes']['points'])!=path_key(move['newPoints']):
     raise verification_error('unit_wire_identity_mismatch','The original native terminal wire was not preserved.')
    aliases=sorted([obj['attributes']['name'],obj['attributes']['location']] for obj in objects
                   if obj['kind']=='alias' and obj['attributes']['wireId']==wires[0]['objectId'])
    if aliases!=move['aliases']:
     raise verification_error('unit_wire_alias_mismatch','An alias changed owner or anchor.')
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
 return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'operation':p['operation'],'unitAware':True,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'unitIdentityVerified':True,'pageGeometryVerified':True,'expectedDefinitionsVerified':True,'nativePageNetworksVerified':True,**({'nativeTerminalWireEditsVerified':True} if p.get('wireEndMoves') else {}),'cachePinMetadataVerified':True,'valueFootprintPreserved':True,'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(writer.config.workspace_root).as_posix(),'notChecked':['incremental_unit_add','cross_page_unit_assignment','full_graphic_cache_identity','flat_occurrence_connectivity','attached_nc_lifecycle','native_drc','rendered_layout']}
