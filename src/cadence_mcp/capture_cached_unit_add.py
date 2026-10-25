"""Missing-device operation of existing durable multiunit placement tasks."""
import copy,json,shutil
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import definition_baseline
from .capture_place import validate_pins
from .capture_references import read_units
from .capture_part_edit import geometry_row
from .capture_geometry import read_part_geometry
from .capture_unit_edit import cache_digest,critical_properties,identities_digest,validate_physical_bindings,IDENTITY
from .capture_multiunit_place import existing_definitions
from .capture_wire import inventory,connection_digest,point
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS,run_tcl,process_env
from .process_tree import run_owned_process
from .isolated_jobs import digest

def target_page(data,owner_part,target_id):
 owner=next(p for p in data['page'] if p['objectId']==owner_part['pageId'])
 page=owner if target_id is None else next((p for p in data['page'] if p['objectId']==target_id),None)
 if page is None:raise CadenceError('object_not_found','Target page is outside this session/revision.')
 if page['schematicId']!=owner['schematicId']:raise CadenceError('unsupported_unit_scope','A physical package may only be extended within its owner schematic.')
 return owner,page

def verify_crosspage_shared_bindings(data,units,bindings,p):
 """Shared physical pads require one actual native network identity, not one label."""
 group={key:u for key,u in units.items() if u['reference']==p['reference'] and u['schematicName']==p['schematicName'] and u['packageName']==p['cacheName']}
 pads={}
 for pin in data['pin']:
  u=group.get(pin['partId'])
  if u is None:continue
  rows=[b for b in bindings if b['kind']=='pin' and b['schematicName']==u['schematicName'] and b['pageName']==u['pageName'] and b['reference']==u['referenceDesignator'] and b['number']==pin['number'] and b['name']==pin['name']]
  if len(rows)!=1:raise CadenceError('cached_unit_shared_native_binding_mismatch','Physical unit pins need unique native binding rows.','verify')
  pads.setdefault(pin['number'],set()).add((rows[0]['group'],rows[0]['netName']))
 if any(len(groups)!=1 for groups in pads.values()):raise CadenceError('cached_unit_shared_native_binding_mismatch','Equal net labels across pages do not prove shared physical-pad connectivity.','verify')

def select_missing_device(cache,identities,owner_id,part_id):
 owner=identities.get(owner_id)
 if owner is None:raise CadenceError('object_not_found','Owner is outside this design session.')
 if not owner['reference'] or '?' in owner['reference']:raise CadenceError('invalid_reference','Assign a stable package reference before adding a missing unit.')
 if owner['kind']!='placed' or owner['packageSize']<2 or owner['isExternalDesignPart']:raise CadenceError('unsupported_unit_scope','Choose an internal multiunit package owner.')
 part=next((p for p in cache['part'] if p['objectId']==part_id),None)
 if part is None:raise CadenceError('object_not_found','View is outside this design cache snapshot.')
 package=next(p for p in cache['package'] if p['objectId']==part['packageId']);device=next(d for d in cache['device'] if d['objectId']==part['deviceId'])
 if package['name']!=owner['packageName'] or package['size']!=owner['packageSize']:raise CadenceError('cache_package_mismatch','Requested device does not belong to the owner package.')
 if not device['designator'] or len(device['designator'])>8:raise CadenceError('unsupported_designator','A bounded nonempty unit designator is required.')
 full_reference=owner['reference']+device['designator']
 group=[u for u in identities.values() if u['reference'].casefold()==owner['reference'].casefold() and u['schematicName']==owner['schematicName']]
 if len({u['deviceDesignator'].casefold() for u in group})!=len(group) or any(u['packageName']!=owner['packageName'] or u['isExternalDesignPart'] or u['kind']!='placed' for u in group):raise CadenceError('ambiguous_package_group','The base reference has conflicting package ownership.')
 if any(u['deviceDesignator'].casefold()==device['designator'].casefold() for u in group) or any(u['referenceDesignator'].casefold()==full_reference.casefold() or u['reference'].casefold()==full_reference.casefold() for u in identities.values()):raise CadenceError('unit_already_placed','This physical package device/full reference is already placed.')
 return owner,package,device,part,group

def plan_cached_unit(writer,sid,owner_id,cache_part_id,location,rotation,mirror,pins,connections,target_page_id=None):
 if not point(location) or type(rotation) is not int or rotation not in range(4) or type(mirror) is not int or mirror not in (0,1):raise CadenceError('invalid_placement','Invalid unit pose.')
 with writer.capture.lock:
  cap=writer.capture;session=cap._session(sid);data=session['data'];identities=read_units(cap,sid);old_cache=cache_digest(cap,sid);cache=session['cacheDefinitions'];owner,package,device,part,group=select_missing_device(cache,identities,owner_id,cache_part_id);source_pins=[p for p in cache['pin'] if p['partId']==part['objectId']];validate_pins(source_pins,pins)
  ownerpart=next(p for p in data['part'] if p['objectId']==owner_id);owner_page,page=target_page(data,ownerpart,target_page_id);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId']);cross_page=owner_page['objectId']!=page['objectId']
  if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity is not unique.')
  properties=[critical_properties(cap,sid,u['partId']) for u in group]
  if any(p!=properties[0] for p in properties) or any(not isinstance(properties[0][k],str) for k in ('Value','PCB Footprint')):raise CadenceError('ambiguous_group_properties','Existing group Value/Footprint must be present and consistent before inheriting them.')
  expected=existing_definitions(data,page['objectId'],connections);oid='planned-cached-unit';expected['part'].append({'objectId':oid,'pageId':page['objectId'],'schematicId':page['schematicId'],'reference':owner['reference']})
  for i,pin in enumerate(pins):expected['pin'].append({'objectId':oid+'/pin-'+str(i),'partId':oid,'pageId':page['objectId'],'schematicId':page['schematicId'],'reference':owner['reference'],'number':pin['number'],'name':pin['name'],'connected':pin['connected'],'net':pin['net'] or ''})
  planned_identity={**owner,'partId':oid,'pageName':page['name'],'deviceDesignator':device['designator'],'referenceDesignator':owner['reference']+device['designator']};validate_physical_bindings(expected,{**identities,oid:planned_identity});pageparts=[p for p in data['part'] if p['pageId'] in {page['objectId'],owner_page['objectId']}]
  if len(pageparts)>100:raise CadenceError('input_limit','Bound original page geometry to100 instances.')
  old_geometry=[{'nativeId':identities[p['objectId']]['nativeId'],'geometry':geometry_row(read_part_geometry(cap,sid,p['objectId'])),'properties':critical_properties(cap,sid,p['objectId'])} for p in pageparts];objects=inventory(cap,sid)
  expected_native=[{'reference':({**identities,oid:planned_identity})[p['partId']]['referenceDesignator'] or ({**identities,oid:planned_identity})[p['partId']]['reference'],'number':p['number'],'name':p['name'],'connected':p['connected'],'net':p['net']} for p in expected['pin'] if p['pageId']==page['objectId']]
  payload={'operation':'add_cached_unit','sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'ownerNativeId':owner['nativeId'],'schematicName':sch['name'],'pageName':page['name'],'reference':owner['reference'],'cacheName':owner['packageName'],'packageSize':owner['packageSize'],'deviceDesignator':device['designator'],'partName':part['name'],'location':location,'rotation':rotation,'mirror':mirror,'value':properties[0]['Value'],'footprint':properties[0]['PCB Footprint'],'expectedPins':copy.deepcopy(pins),'oldPageGeometry':old_geometry,'expectedNativePins':expected_native,'identityDigest':identities_digest(identities),'expectedDefinitionDigest':definition_baseline(expected),'expectedConnectionDigest':connection_digest(data,objects),'cacheDigest':old_cache}
  if cross_page:
   from .capture_cache_replace import read_state
   if len(identities)>=128:raise CadenceError('input_limit','Cross-page complete modeled state permits at most127 original instances.')
   payload.update(ownerPageName=owner_page['name'],crossPage=True,originalInstanceStateDigest=digest(read_state(writer.config,session['design'],session['design'].parent,identities)))
  if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>160000:raise CadenceError('plan_limit','Missing-unit baseline exceeds durable bounds.')
  cap._session(sid);return writer.create_plan(payload)

def execute_cached_unit(writer,directory,p,cancel,on_started):
 writer.preflight(p);source=checked_path(p['sourceDesign'],(writer.config.workspace_root,))
 with source.open('rb') as original,(directory/'design.dsn').open('xb') as target:shutil.copyfileobj(original,target)
 if sha256(source)!=p['sourceFingerprint'] or sha256(directory/'design.dsn')!=p['sourceFingerprint']:raise CadenceError('target_changed','Design changed during missing-unit copy.')
 with (directory/'cached-unit-request.json').open('x',encoding='utf-8') as f:json.dump(p,f,ensure_ascii=False,separators=(',',':'))
 return run_owned_process([writer.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'add_cached_unit.tcl',writer.config.install_root,directory/'design.dsn',directory/'cached-unit-request.json',directory/'native-result.json'],directory,process_env(writer.config),writer.config.timeout_seconds,cancel=cancel,on_started=on_started)

def verify_cached_unit(writer,directory,p,native_completed):
 def error(code,message):return CadenceError(code,message,'verify')
 target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
 if target.stat().st_size>128*1024*1024:raise error('output_limit','Missing-unit output exceeds size bound.')
 if native_completed:
  receipt=directory/'native-result.json'
  if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True}:raise error('invalid_worker_result','Missing-unit receipt mismatch.')
 cap=CaptureService(writer.config);cap.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}};sid=cap.open('output')['sessionId']
 try:
  data=cap.sessions[sid]['data']
  if definition_baseline(data)!=p['expectedDefinitionDigest']:raise error('cached_unit_definition_mismatch','Saved definitions or pin/net mappings differ from declaration.')
  if connection_digest(data,inventory(cap,sid))!=p['expectedConnectionDigest']:raise error('cached_unit_connections_changed','Saved wires/labels/connection objects changed.')
  units=read_units(cap,sid);added=[u for u in units.values() if u['reference']==p['reference'] and u['referenceDesignator']==p['reference']+p['deviceDesignator'] and u['deviceDesignator']==p['deviceDesignator'] and u['packageName']==p['cacheName'] and u['packageSize']==p['packageSize'] and u['schematicName']==p['schematicName'] and u['pageName']==p['pageName'] and u['kind']=='placed' and not u['isExternalDesignPart']]
  if len(added)!=1:raise error('cached_unit_identity_mismatch','Added device is not uniquely owned by the original group.')
  unit=added[0];remaining={key:u for key,u in units.items() if u['partId']!=unit['partId']}
  if identities_digest(remaining)!=p['identityDigest']:raise error('cached_unit_prior_identity_changed','An original instance identity changed.')
  if p.get('crossPage'):
   from .capture_cache_replace import read_state
   original_state=[row for row in read_state(writer.config,target,directory,units) if row['nativeId']!=unit['nativeId']]
   if digest(original_state)!=p['originalInstanceStateDigest']:raise error('cached_unit_prior_state_changed','Original instance geometry or effective/user/display property state changed.')
  expected_geometry={'location':p['location'],'rotationCode':p['rotation'],'mirrorCode':p['mirror'],'pins':sorted([{k:v[k] for k in ('number','name','hotSpot')} for v in p['expectedPins']],key=lambda v:(v['number'],v['name']))}
  if geometry_row(read_part_geometry(cap,sid,unit['partId']))!=expected_geometry:raise error('cached_unit_hotspot_mismatch','Restored unit pose/hotspots differ from caller declaration.')
  if critical_properties(cap,sid,unit['partId'])!={'Value':p['value'],'PCB Footprint':p['footprint']}:raise error('cached_unit_properties_mismatch','Added unit lost inherited group Value/Footprint.')
  for old in p['oldPageGeometry']:
   selected=[u for u in remaining.values() if u['nativeId']==old['nativeId']]
   if len(selected)!=1 or geometry_row(read_part_geometry(cap,sid,selected[0]['partId']))!=old['geometry'] or critical_properties(cap,sid,selected[0]['partId'])!=old['properties']:raise error('cached_unit_prior_geometry_changed','An original page unit pose or Value/Footprint changed.')
  if cache_digest(cap,sid)!=p['cacheDigest']:raise error('cached_unit_cache_changed','Existing cache mapping/metadata changed.')
  view=directory/'restored-unit-view.json'
  if view.exists():view.unlink()
  run_tcl(writer.config,'inspect_cached_unit_view.tcl',[str(target),str(view),p['schematicName'],p['pageName'],str(unit['nativeId'])],directory)
  if json.loads(view.read_text(encoding='utf-8'))!={'partName':p['partName']}:raise error('cached_unit_view_mismatch','Saved unit uses a different cached part view.')
  out=directory/'restored-native-bindings.json'
  if out.exists():out.unlink()
  run_tcl(writer.config,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],directory);bindings=json.loads(out.read_text(encoding='utf-8'));groups={}
  if p.get('crossPage'):verify_crosspage_shared_bindings(data,units,bindings,p)
  for pin in p['expectedNativePins']:
   rows=[b for b in bindings if b['kind']=='pin' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and all(b[k]==pin[k] for k in ('reference','number','name'))]
   if len(rows)!=1 or (rows[0]['group'] is not None)!=pin['connected'] or rows[0]['netName']!=pin['net']:raise error('cached_unit_native_binding_mismatch','A page pin differs from native network expectations.')
   if pin['connected']:groups.setdefault(pin['net'],set()).add(rows[0]['group'])
  for name,group in groups.items():
   group.update(b['group'] for b in bindings if b['kind']=='wire' and b['schematicName']==p['schematicName'] and b['pageName']==p['pageName'] and b['netName']==name)
   if len(group)!=1 or None in group:raise error('cached_unit_native_network_mismatch','Declared page pin/wire members do not share one native network.')
  if len({next(iter(g)) for g in groups.values()})!=len(groups):raise error('cached_unit_native_network_mismatch','Distinct expected nets unexpectedly merge.')
 finally:cap.close(sid)
 writer.preflight(p)
 if sha256(target)!=before:raise error('target_changed','Restored output changed during verification.')
 ident=directory.name.removeprefix('plan-');artifact={'artifactId':'cached-unit-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
 return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'operation':'add_cached_unit','nativeCompletionVerified':native_completed,'independentReopenVerified':True,'unitOwnershipVerified':True,'cachedViewVerified':True,'cachePinMetadataPreserved':True,'nativePageNetworksVerified':True,'originalPageGeometryVerified':True,'crossPageUnitAssignmentVerified':bool(p.get('crossPage')),'allOriginalModeledInstanceStateVerified':bool(p.get('crossPage')),'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(writer.config.workspace_root).as_posix(),'notChecked':([] if p.get('crossPage') else ['cross_page_unit_assignment'])+['full_graphic_cache_identity','flat_occurrence_connectivity','display_font_preservation','external_cache_closure','native_drc','rendered_layout']}
