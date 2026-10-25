"""Explicit reference maps/swaps with collision preflight and source pin invariants."""
import copy,json,re
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_part_edit import page_geometry
from .capture_wire import inventory,connection_digest
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,run_tcl,process_env
from .process_tree import run_owned_process

REF=re.compile(r'([A-Za-z][A-Za-z_]*)([1-9][0-9]{0,8})\Z')
def reference_map(data,mappings):
    if not isinstance(mappings,list) or not 1<=len(mappings)<=64:raise CadenceError('invalid_reference_map','Provide 1..64 explicit part mappings.')
    by_id={p['objectId']:p for p in data['part']};selected={};destinations=set()
    counts={}
    for p in data['part']:counts[p['reference'].casefold()]=counts.get(p['reference'].casefold(),0)+1
    for row in mappings:
        if not isinstance(row,dict) or set(row)!={'partId','newReference'} or not isinstance(row['partId'],str) or not isinstance(row['newReference'],str):raise CadenceError('invalid_reference_map','Invalid typed reference mapping.')
        part=by_id.get(row['partId'])
        if part is None:raise CadenceError('object_not_found','Mapped part is outside this session.')
        if row['partId'] in selected:raise CadenceError('invalid_reference_map','Each part may appear once.')
        before=REF.fullmatch(part['reference']);after=REF.fullmatch(row['newReference'])
        if not before or not after or len(row['newReference'])>64 or before[1].casefold()!=after[1].casefold():raise CadenceError('invalid_reference','Use a numbered reference with the existing prefix; unnumbered/multiunit allocation needs its dedicated operation.')
        if counts[part['reference'].casefold()]!=1:raise CadenceError('ambiguous_reference','Repeated definition references require a package/occurrence-aware map.')
        if part['reference']==row['newReference']:raise CadenceError('no_change','Mapping contains an unchanged reference.')
        folded=row['newReference'].casefold()
        if folded in destinations:raise CadenceError('reference_conflict','Final mapped references must be unique, ignoring case.')
        destinations.add(folded);selected[row['partId']]=row['newReference']
    if any(p['reference'].casefold() in destinations for p in data['part'] if p['objectId'] not in selected):raise CadenceError('reference_conflict','A destination reference is owned by an unmapped part.')
    expected=copy.deepcopy(data)
    for kind in ('part','pin'):
        for p in expected[kind]:
            identity=p['objectId'] if kind=='part' else p['partId']
            if identity in selected:p['reference']=selected[identity]
    reserved={p['reference'].casefold() for p in data['part']}|destinations;temporary={}
    for identity,new in selected.items():
        prefix=REF.fullmatch(by_id[identity]['reference'])[1];number=900000000
        while (prefix+str(number)).casefold() in reserved:number+=1
        if number>999999999:raise CadenceError('reference_conflict','No bounded temporary reference is available.')
        value=prefix+str(number);temporary[identity]=value;reserved.add(value.casefold())
    return selected,temporary,expected

def read_units(capture,sid):
    session=capture._session(sid);out=session['design'].parent/(new_id('reference-units')+'.json')
    run_tcl(capture.config,'inspect_reference_units.tcl',[str(session['design']),str(out)],out.parent)
    capture._session(sid)
    try:
        if out.stat().st_size>16*1024*1024:raise ValueError()
        rows=json.loads(out.read_text(encoding='utf-8'));parts={p['objectId']:p for p in session['data']['part']}
        if not isinstance(rows,list) or len(rows)!=len(parts):raise ValueError()
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or row.get('partId') not in parts or row['partId'] in seen or row.get('reference')!=parts[row['partId']]['reference'] or row.get('kind') not in ('placed','drawn') or type(row.get('nativeId')) is not int or type(row.get('packageSize')) is not int or type(row.get('isExternalDesignPart')) is not bool:raise ValueError()
            if any(not isinstance(row.get(k),str) for k in ('schematicName','pageName','packageName','deviceDesignator','referenceDesignator','sourceLib','sourcePart')):raise ValueError()
            seen.add(row['partId'])
    except (OSError,ValueError,TypeError,KeyError) as e:raise CadenceError('invalid_worker_result','Invalid native reference identity document.','decode') from e
    out.unlink();return {r['partId']:r for r in rows}

class CaptureReferenceEdits(CapturePropertyEdits):
    kind='capture_reference'
    max_record_bytes=256*1024
    def plan_packages(self,sid,mappings):
        from .capture_package_references import plan_package_references
        return plan_package_references(self,sid,mappings)
    def plan(self,sid,mappings):
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];selected,temporary,expected=reference_map(data,mappings)
            units=read_units(self.capture,sid);objects=inventory(self.capture,sid);parts={p['objectId']:p for p in data['part']}
            if any(o['kind']=='nc' and o['attributes'].get('partId') in selected for o in objects):raise CadenceError('attached_nc_unsupported','Mapped NC ownership needs explicit package-aware validation.')
            changes=[];geometry=[];names={s['objectId']:s['name'] for s in data['schematic']};page_ids={parts[k]['pageId'] for k in selected}
            for key,new in selected.items():
                unit=units[key]
                if unit['isExternalDesignPart']:raise CadenceError('unsupported_reference_scope','External design part references need verified dependency closure.')
                if unit['kind']!='placed' or unit['packageSize']!=1:raise CadenceError('unsupported_reference_scope','This map supports single-unit placed definitions; package/occurrence changes remain separate.')
                if any(len(unit[k])>512 or '\x00' in unit[k] for k in ('schematicName','pageName','packageName')):raise CadenceError('input_limit','Reference locator exceeds literal bounds.')
                changes.append({k:unit[k] for k in ('partId','nativeId','schematicName','pageName','packageName')}|{'oldReference':unit['reference'],'newReference':new,'temporaryReference':temporary[key]})
            for pid in page_ids:
                page=next(p for p in data['page'] if p['objectId']==pid);sch=names[page['schematicId']]
                if sum(s['name']==sch for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic locator is not unique.')
                before=page_geometry(self.capture,sid,pid);renamed={selected.get(p['objectId'],p['reference']):before[p['reference']] for p in data['part'] if p['pageId']==pid}
                geometry.append({'schematicName':sch,'pageName':page['name'],'parts':renamed})
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'changes':changes,'expectedGeometry':geometry,
                     'expectedDefinitionDigest':definition_baseline(expected),'connectionDigest':connection_digest(data,objects)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Reference map baseline exceeds durable record bound.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('mode','changes','pinNodeMap','sourceFingerprint','expectedGeometry') if k in p}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Reference map source changed after planning.')
        if p.get('mode')=='package_groups_v1' and sha256(checked_path(p['expectedEvidence'],(self.config.workspace_root,)))!=p['expectedEvidenceHash']:raise CadenceError('target_changed','Frozen package reference expectation changed.')
    def execute(self,directory,p,cancel,on_started):
        # Keep base immutable copy checks; the fixed worker consumes a JSON declaration.
        write_json(directory/'references.json',{'changes':p['changes']})
        return super().execute(directory,p,cancel,on_started)
    def native_command(self,directory,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/('edit_package_references.tcl' if p.get('mode')=='package_groups_v1' else 'edit_references.tcl'),self.config.install_root,directory/'design.dsn',directory/'references.json',directory/'native-result.json']
    def verify(self,directory,p,native_completed):
        if p.get('mode')=='package_groups_v1':
            from .capture_package_references import verify_package_references
            return verify_package_references(self,directory,p,native_completed)
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Reference output exceeds limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'reference_mapping','changed':len(p['changes'])}:raise CadenceError('invalid_worker_result','Reference save receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('reference_connectivity_mismatch','Saved references/pins/nets differ from the explicit reference map.','verify')
            if connection_digest(data,inventory(verifier,sid))!=p['connectionDigest']:raise CadenceError('reference_connection_objects_changed','Reference map changed connection objects.','verify')
            sch={s['objectId']:s['name'] for s in data['schematic']}
            for wanted in p['expectedGeometry']:
                pages=[pg for pg in data['page'] if pg['name']==wanted['pageName'] and sch[pg['schematicId']]==wanted['schematicName']]
                if len(pages)!=1 or page_geometry(verifier,sid,pages[0]['objectId'])!=wanted['parts']:raise CadenceError('reference_geometry_mismatch','Mapped references do not retain the expected part and pin geometry.','verify')
            units=read_units(verifier,sid)
            for change in p['changes']:
                rows=[u for u in units.values() if (u['schematicName'],u['pageName'],u['reference'])==(change['schematicName'],change['pageName'],change['newReference'])]
                if len(rows)!=1 or rows[0]['kind']!='placed' or rows[0]['packageName']!=change['packageName'] or rows[0]['packageSize']!=1 or rows[0]['referenceDesignator']!=change['newReference']:raise CadenceError('reference_package_mismatch','Mapped single-unit package identity changed.','verify')
        finally:verifier.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Reference output changed during verification.')
        ident=directory.name.removeprefix('plan-');artifact={'artifactId':'references-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'referenceMap':p['changes'],'sourceModified':False,'scope':'single_unit_part_definitions','designPassed':None,'occurrenceConnectivityVerified':False,
                'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'definitionPinNetAndGeometryVerified':True,
                'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['external_design_closure','multiunit_package_mapping','occurrence_reference_mapping','native_automatic_annotation','unnumbered_allocation','display_text_rendering','other_part_properties','native_drc']}
