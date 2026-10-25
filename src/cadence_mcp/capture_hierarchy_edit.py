"""Durable internal hierarchy-block reuse with native partition verification."""
import copy,json,re
from pathlib import Path
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_part_edit import page_geometry,declared_pose
from .capture_hierarchy import get_hierarchy
from .capture_properties import read_part_properties
from .capture_references import read_units
from .capture_wire import inventory,connection_digest,point
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,run_tcl
from .hierarchy_semantics import native_partition_rows,net_partition,verify_reused_context
from .isolated_jobs import digest

def tree_rows(capture,sid):
    get_hierarchy(capture,sid,None,1000)
    return capture._session(sid)['hierarchy']

def tree_digest(rows):
    return digest(sorted([{'path':r['instancePathSegments'],'properties':sorted(r['properties'],key=lambda p:p['name'])} for r in rows],key=lambda r:json.dumps(r['path'])))

def read_flat(capture,sid):
    session=capture._session(sid);directory=capture._workspace(session['workspaceId'])['directory'];out=directory/(new_id('hierarchy-flat')+'.json')
    run_tcl(capture.config,'inspect_occurrence_nets.tcl',[str(session['design']),str(out)],directory);capture._session(sid)
    if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Native flat pin evidence exceeds limit.')
    try:
        raw=json.loads(out.read_text(encoding='utf-8'))
        if not isinstance(raw,dict) or set(raw)!={'occurrenceCount','flatNetCount','pins'} or type(raw['occurrenceCount']) is not int or type(raw['flatNetCount']) is not int:raise ValueError('shape')
        rows=native_partition_rows(raw['pins'])
        if raw['occurrenceCount']!=len(tree_rows(capture,sid)) or raw['flatNetCount']!=len({p['flatNetId'] for p in rows if p['flatNetId'] is not None}):raise ValueError('counts')
    except (ValueError,TypeError,KeyError) as e:raise CadenceError('invalid_worker_result','Incomplete native flat partition document.','decode') from e
    out.unlink();return rows

class CaptureHierarchyEdits(CapturePropertyEdits):
    kind='capture_hierarchy_clone'
    def plan(self,sid,part_id,new_reference,location,expected_pins):
        if not isinstance(new_reference,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',new_reference) or not point(location):
            raise CadenceError('invalid_hierarchy_clone','Use a bounded literal reference and integer point.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];part=next((p for p in data['part'] if p['objectId']==part_id),None)
            if part is None:raise CadenceError('object_not_found','Source block is outside this session.')
            if any(p['reference'].casefold()==new_reference.casefold() for p in data['part']):raise CadenceError('reference_conflict','New block reference already exists in this definition design.')
            units=read_units(self.capture,sid);unit=units[part_id]
            if unit['kind']!='drawn' or any(u['isExternalDesignPart'] for u in units.values()):raise CadenceError('unsupported_hierarchy_scope','Clone needs a drawn internal block and no external design parts.')
            page=next(p for p in data['page'] if p['objectId']==part['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==part['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity is not unique.')
            rows=tree_rows(self.capture,sid);source=[r for r in rows if r['instancePathSegments']==[part['reference']]]
            if len(source)!=1:raise CadenceError('unsupported_hierarchy_scope','This operation requires a uniquely resolved top-level block occurrence.')
            props={p['name']:p['value'] for p in source[0]['properties']}
            implementation=props.get('Implementation','')
            if props.get('Implementation Type')!='Schematic View' or props.get('Implementation Path') or not implementation or sum(s['name']==implementation for s in data['schematic'])!=1:
                raise CadenceError('unsupported_hierarchy_scope','A uniquely resolved internal schematic implementation is required.')
            if any(next((p['value'] for p in row['properties'] if p['name']=='Implementation Path'),'') for row in rows):raise CadenceError('unsupported_hierarchy_scope','External implementation paths are not accepted.')
            subtree=[r['instancePathSegments'] for r in rows if r['instancePathSegments'] and r['instancePathSegments'][0]==part['reference']]
            if len(subtree)<2:raise CadenceError('unsupported_hierarchy_scope','Source block has no resolved child instances.')
            if any(r['instancePathSegments'] and r['instancePathSegments'][0]==new_reference for r in rows):raise CadenceError('reference_conflict','New occurrence context already exists.')
            geometry=page_geometry(self.capture,sid,page['objectId']);old=geometry[part['reference']]
            if not old['pins'] or len({(p['number'],p['name']) for p in old['pins']})!=len(old['pins']):raise CadenceError('ambiguous_target','Source boundary pins need distinct scalar identities.')
            pose=declared_pose(old,location,old['rotationCode'],old['mirrorCode'],expected_pins);geometry[new_reference]=pose
            objects=inventory(self.capture,sid)
            if any(o['kind']=='nc' and o['attributes'].get('partId')==part_id for o in objects):raise CadenceError('attached_nc_unsupported','Source NC markers require separate lifecycle handling.')
            expected=copy.deepcopy(data);oid=part_id+'/clone';expected['part'].append({**part,'objectId':oid,'reference':new_reference})
            for i,pin in enumerate([p for p in data['pin'] if p['partId']==part_id]):expected['pin'].append({**pin,'objectId':oid+'/pin-'+str(i+1),'partId':oid,'reference':new_reference,'connected':False,'net':''})
            before_flat=read_flat(self.capture,sid)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'partId':part_id,'nativeId':unit['nativeId'],'schematicName':sch['name'],'pageName':page['name'],'sourceReference':part['reference'],'newReference':new_reference,'location':location,'expectedGeometry':geometry,'expectedDefinitionDigest':definition_baseline(expected),'connectionDigest':connection_digest(data,objects),'originalTreeDigest':tree_digest(rows),'originalPartitionDigest':digest(net_partition(before_flat)),'expectedAddedPaths':[[new_reference,*p[1:]] for p in subtree],'implementationFields':{k:props.get(k,'') for k in ('Value','Primitive','Implementation Type','Implementation','Implementation Path')},'sharedGlobalNames':sorted({p['flatNetName'] for p in before_flat if p['isGlobal']})}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Hierarchy clone plan exceeds durable bounds.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('partId','sourceReference','newReference','schematicName','pageName','location','implementationFields','expectedAddedPaths','sourceFingerprint','expectedGeometry')}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower()!='.dsn' or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Hierarchy source differs from its immutable plan.')
    def execute(self,directory,p,cancel,on_started):
        self.preflight(p);write_json(directory/'hierarchy-clone.json',{k:p[k] for k in ('nativeId','schematicName','pageName','sourceReference','newReference','location')});return super().execute(directory,p,cancel,on_started)
    def native_command(self,directory,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_hierarchy_clone.tcl',self.config.install_root,directory/'design.dsn',directory/'hierarchy-clone.json',directory/'native-result.json']
    def verify(self,directory,p,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Hierarchy output exceeds limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'clone_internal_block'}:raise CadenceError('invalid_worker_result','Hierarchy clone save receipt mismatch.')
        self.preflight(p);verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['expectedDefinitionDigest'] or connection_digest(data,inventory(verifier,sid))!=p['connectionDigest']:raise CadenceError('hierarchy_definition_mismatch','Saved block boundary pins or original definition/connection objects differ.','verify')
            names={s['objectId']:s['name'] for s in data['schematic']};pages=[pg for pg in data['page'] if pg['name']==p['pageName'] and names[pg['schematicId']]==p['schematicName']]
            if len(pages)!=1 or page_geometry(verifier,sid,pages[0]['objectId'])!=p['expectedGeometry']:raise CadenceError('hierarchy_geometry_mismatch','Saved page parts and boundary pin hotspots differ.','verify')
            tree=tree_rows(verifier,sid);old=[r for r in tree if not r['instancePathSegments'] or r['instancePathSegments'][0]!=p['newReference']];new=[r for r in tree if r['instancePathSegments'] and r['instancePathSegments'][0]==p['newReference']]
            if tree_digest(old)!=p['originalTreeDigest'] or sorted([r['instancePathSegments'] for r in new])!=sorted(p['expectedAddedPaths']):raise CadenceError('hierarchy_tree_mismatch','Original occurrence properties or the cloned subtree differ.','verify')
            root=next(r for r in new if r['instancePathSegments']==[p['newReference']]);props={x['name']:x['value'] for x in root['properties']}
            if any(props.get(k,'')!=v for k,v in p['implementationFields'].items()):raise CadenceError('hierarchy_implementation_mismatch','Cloned internal implementation fields differ.','verify')
            source_reader=CaptureService(self.config);source_reader.workspaces['source']={'directory':Path(p['sourceDesign']).parent,'manifest':{'copiedFingerprint':p['sourceFingerprint']}}
            source_sid=source_reader.open('source')['sessionId']
            try:source_flat=read_flat(source_reader,source_sid)
            finally:source_reader.close(source_sid)
            if digest(net_partition(source_flat))!=p['originalPartitionDigest']:raise CadenceError('target_changed','Source native partition differs from planned evidence.')
            partition_checks=verify_reused_context(source_flat,read_flat(verifier,sid),p['sourceReference'],p['newReference'],set(p['sharedGlobalNames']))
        finally:verifier.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Hierarchy output changed during independent reads.')
        ident=directory.name.removeprefix('plan-');artifact={'artifactId':'hierarchy-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'sourceModified':False,'scope':'top_level_internal_block_reuse','partitionChecks':partition_checks,'originalOccurrencePropertiesVerified':True,'designPassed':None,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['new_child_definition_creation','port_crud','nested_source_blocks','external_design_closure','annotation_package_ownership','new_occurrence_property_overrides','other_page_geometry','all_definition_properties','rendering','native_drc']}
