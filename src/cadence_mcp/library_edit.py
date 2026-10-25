"""Explicit symbol pin edits and device pad mappings on new OLB output copies."""
from datetime import datetime,timezone
import copy,json,re,shutil
from .core import CadenceError,checked_path,sha256,new_id,write_json,Config
from .environment import ADAPTERS,process_env,run_tcl
from .process_tree import run_owned_process
from .isolated_jobs import IsolatedJobs,digest
from .library import validate_library,LibraryService
from .library_semantics import library_graph


def expected_library(data,pin_id,name=None,number=None,pin_type=None,hot_spot=None,visible=None):
    if name is not None and (not isinstance(name,str) or not 1<=len(name)<=128 or re.search(r'[\x00-\x1f\x7f]',name)):
        raise CadenceError('invalid_pin_edit','Pin name must be a bounded non-control string.')
    if number is not None and (not isinstance(number,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,31}',number)):
        raise CadenceError('invalid_pin_edit','Pad number must be a bounded literal identifier.')
    if pin_type is not None and (type(pin_type) is not int or not 0<=pin_type<=7):
        raise CadenceError('invalid_pin_edit','Pin type code must be an integer in the documented eight-type range.')
    if hot_spot is not None and (not isinstance(hot_spot,list) or len(hot_spot)!=2 or any(type(v) is not int or abs(v)>1000000 for v in hot_spot)):
        raise CadenceError('invalid_pin_edit','Hotspot requires two integer coordinates within +/-1000000.')
    if visible is not None and type(visible) is not bool:raise CadenceError('invalid_pin_edit','Visibility requires a boolean.')
    if name is None and number is None and pin_type is None and hot_spot is None and visible is None:raise CadenceError('invalid_pin_edit','At least one pin field is required.')
    target=next((p for p in data['pin'] if p['objectId']==pin_id),None)
    if target is None:raise CadenceError('object_not_found','Pin does not belong to this library snapshot.')
    parts={p['objectId']:p for p in data['part']};cells={p['objectId']:p for p in data['cell']}
    def symbol_key(pin):
        part=parts[pin['partId']];return (cells[part['cellId']]['name'],part['name'],pin['position'])
    key=symbol_key(target)
    if number is not None:
        conflicts=[p for p in data['pin'] if p['packageId']==target['packageId'] and p['number']==number
                   and (p['deviceId'],p['position'])!=(target['deviceId'],target['position'])]
        if conflicts:raise CadenceError('pad_number_conflict','Requested pad number is already mapped elsewhere in this package; shared-pin changes need a dedicated mapping operation.')
        if target['shared'] and number!=target['number']:raise CadenceError('shared_pin_mapping','Shared pad renumbering requires a package-wide shared-pin mapping operation.')
    expected=copy.deepcopy(data);affected=[]
    for row in expected['pin']:
        before=copy.deepcopy(row)
        if symbol_key(row)==key:
            if name is not None:row['name']=name
            if pin_type is not None:row['pinType']=pin_type
            if hot_spot is not None:row['hotSpot']=copy.deepcopy(hot_spot)
            if visible is not None:row['visible']=visible
        if number is not None and (row['deviceId'],row['position'])==(target['deviceId'],target['position']):row['number']=number
        if row!=before:affected.append({'pinId':row['objectId'],'old':before,'expected':copy.deepcopy(row)})
    if name is not None or pin_type is not None:
        shared={}
        for row in expected['pin']:
            if row['shared']:shared.setdefault((row['packageId'],row['number']),set()).add((row['name'],row['pinType']))
        old_shared={}
        for row in data['pin']:
            if row['shared']:old_shared.setdefault((row['packageId'],row['number']),set()).add((row['name'],row['pinType']))
        if any(len(values)>1 and values!=old_shared.get(key) for key,values in shared.items()):raise CadenceError('shared_pin_function_conflict','Changing one heterogeneous shared-pad function requires a package-wide operation.')
    if not affected:raise CadenceError('no_change','Requested pin fields already match the snapshot.')
    return target,expected,affected


def expected_pin_start(graph,cell_name,part_name,position,start_point):
    if not isinstance(start_point,list) or len(start_point)!=2 or any(type(v) is not int or abs(v)>1000000 for v in start_point):
        raise CadenceError('invalid_pin_edit','Start point requires two integer coordinates within +/-1000000.')
    expected=copy.deepcopy(graph);changes=[];old_points=[]
    for row in expected['metadata']['symbols']:
        if row['scope'][-2:]!=[cell_name,part_name]:continue
        matches=[p for p in row['pinStarts'] if p['position']==position]
        if len(matches)!=1:raise CadenceError('ambiguous_library_graph','Every referenced target symbol must contain exactly one matching pin start.')
        pin=matches[0];old_points.append(pin['start'])
        if pin['start']!=start_point:
            changes.append({'scope':copy.deepcopy(row['scope']),'position':position,'oldStartPoint':copy.deepcopy(pin['start']),'expectedStartPoint':copy.deepcopy(start_point)})
            pin['start']=copy.deepcopy(start_point)
    if not old_points or any(p!=old_points[0] for p in old_points):raise CadenceError('ambiguous_library_graph','Shared symbol pin starts must agree across all referenced views.')
    if len(changes)>64:raise CadenceError('affected_limit','More than64 pin-start view rows would change.')
    return expected,changes,copy.deepcopy(old_points[0])


class LibraryPinEdits(IsolatedJobs):
    kind='library_pin'
    def __init__(self,config,library):super().__init__(config);self.library=library

    def plan(self,library_id,pin_id,name=None,number=None,pin_type=None,hot_spot=None,visible=None,start_point=None):
        with self.library.lock:
            session=self.library._session(library_id)
            data=session['data']
            fields_requested=any(v is not None for v in (name,number,pin_type,hot_spot,visible))
            if start_point is not None and not fields_requested:
                target=next((p for p in data['pin'] if p['objectId']==pin_id),None)
                if target is None:raise CadenceError('object_not_found','Pin does not belong to this library snapshot.')
                expected=copy.deepcopy(data);affected=[]
            else:
                try:target,expected,affected=expected_library(data,pin_id,name,number,pin_type,hot_spot,visible)
                except CadenceError as error:
                    if error.code!='no_change' or start_point is None:raise
                    target=next(p for p in data['pin'] if p['objectId']==pin_id);expected=copy.deepcopy(data);affected=[]
            package=next(p for p in data['package'] if p['objectId']==target['packageId'])
            device=next(p for p in data['device'] if p['objectId']==target['deviceId'])
            part=next(p for p in data['part'] if p['objectId']==target['partId'])
            cell=next(p for p in data['cell'] if p['objectId']==part['cellId'])
            if len(affected)>64:raise CadenceError('affected_limit','More than 64 duplicated symbol/device pin rows would change.')
            payload={'sourceLibrary':str(session['directory']/'library.olb'),'sourceFingerprint':session['revision'],
                     'pinId':pin_id,'old':target,'name':name,'number':number,'pinType':pin_type,
                     'comparison':'semantic_graph_v1','expectedLibraryDigest':digest(library_graph(expected)),'beforeLibraryDigest':digest(library_graph(session['data'])),
                     'targetIdentity':{'packageName':package['name'],'deviceDesignator':device['designator'],
                                       'cellName':cell['name'],'partName':part['name'],'devicePosition':device['position']},
                     'affected':affected}
            if hot_spot is not None or visible is not None or start_point is not None:
                graph=self._pin_graph(session['directory']/'library.olb',session['directory'])
                if graph['definitions']!=library_graph(data):raise CadenceError('target_changed','Library graph differs from the bound snapshot.')
                graph['definitions']=library_graph(expected)
                if start_point is not None:
                    graph,start_changes,old_start=expected_pin_start(graph,cell['name'],part['name'],target['position'],start_point)
                    if not affected and not start_changes:raise CadenceError('no_change','Requested pin fields and start point already match the snapshot.')
                    payload.update(startPoint=start_point,oldStartPoint=old_start,affectedStartPoints=start_changes)
                payload.update(hotSpot=hot_spot,visible=visible,expectedGraphDigest=digest(graph))
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:
                raise CadenceError('plan_limit','Pin plan exceeds the bounded durable-record size.')
            self.library._session(library_id)
            return self.create_plan(payload)

    def _pin_graph(self,source,directory):
        from .library_vector_edit import vector_graph
        output=directory/(new_id('pin-preservation')+'.json')
        run_tcl(self.config,'inspect_library_create.tcl',[str(source),str(output),'100000','1'],directory)
        if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Library preservation graph exceeds32MiB.')
        return vector_graph(json.loads(output.read_text(encoding='utf-8')))

    def preview(self,payload):
        return {k:payload[k] for k in ('pinId','old','name','number','pinType','sourceFingerprint','targetIdentity','affected','hotSpot','visible','startPoint','oldStartPoint','affectedStartPoints') if k in payload}

    def preflight(self,payload):
        if payload.get('comparison')!='semantic_graph_v1':raise CadenceError('legacy_plan_requires_review','Prepare a new semantic plan; started legacy jobs must never be replayed.')
        source=checked_path(payload['sourceLibrary'],(self.config.workspace_root,))
        if source.suffix.lower()!='.olb' or sha256(source)!=payload['sourceFingerprint']:
            raise CadenceError('target_changed','Library snapshot changed after planning.')

    def execute(self,directory,payload,cancel,on_started):
        self.preflight(payload)
        source=checked_path(payload['sourceLibrary'],(self.config.workspace_root,));target=directory/'library.olb'
        with source.open('rb') as original,target.open('xb') as copied:shutil.copyfileobj(original,copied)
        if sha256(target)!=payload['sourceFingerprint'] or sha256(source)!=payload['sourceFingerprint']:
            raise CadenceError('target_changed','Library changed during isolated copy.')
        old=payload['old']
        spec={'targetPin':payload['pinId'],'expectedName':old['name'],'expectedNumber':old['number'],
              'expectedType':old['pinType'],'expectedPosition':old['position'],'identity':payload['targetIdentity'],
              'changeName':payload['name'] is not None,'newName':payload['name'] or '',
              'changeNumber':payload['number'] is not None,'newNumber':payload['number'] or '',
              'changeType':payload['pinType'] is not None,'newType':payload['pinType'] if payload['pinType'] is not None else 0}
        if 'expectedGraphDigest' in payload:
            spec.update(changeHotSpot=payload['hotSpot'] is not None,newHotSpot=payload['hotSpot'] or [0,0],
                        changeVisible=payload['visible'] is not None,newVisible=payload['visible'] or False,
                        expectedHotSpot=old['hotSpot'],expectedVisible=old['visible'])
        if 'startPoint' in payload:
            spec.update(changeStartPoint=True,newStartPoint=payload['startPoint'],expectedStartPoint=payload['oldStartPoint'])
        write_json(directory/'pin-edit.json',spec)
        argv=[self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_library_pin.tcl',self.config.install_root,
              target,directory/'pin-edit.json',directory/'native-result.json']
        return run_owned_process(argv,directory,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)

    def verify(self,directory,payload,native_completed):
        target=checked_path(str(directory/'library.olb'),(directory,));before=sha256(target)
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'pinId':payload['pinId']}:
                raise CadenceError('invalid_worker_result','Native library save receipt mismatch.','verify')
        output=directory/(new_id('verification')+'.json')
        run_tcl(self.config,'inspect_library.tcl',[str(target),str(output),'100000'],directory)
        if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Library verification result exceeds limit.')
        data=json.loads(output.read_text(encoding='utf-8'));validate_library(data)
        if payload.get('comparison')!='semantic_graph_v1':raise CadenceError('legacy_plan_requires_review','Legacy ordinal-based library plans require explicit migration; never replay them.')
        if digest(library_graph(data))!=payload['expectedLibraryDigest']:
            raise CadenceError('library_verification_failed','Reopened library differs from the planned symbol/device mapping; unrelated definitions must be preserved.','verify')
        if 'expectedGraphDigest' in payload and digest(self._pin_graph(target,directory))!=payload['expectedGraphDigest']:
            raise CadenceError('library_preservation_failed','Reopened pin geometry, start points, templates or modeled vectors differ from the declared edit.','verify')
        self.preflight(payload)
        if sha256(target)!=before:raise CadenceError('target_changed','Library changed during verification.')
        plan_id=directory.name.removeprefix('plan-')
        artifact={'artifactId':'library-'+plan_id,'kind':'capture_edited_library','workspaceRelativePath':'library.olb',
                  'sha256':before,'size':target.stat().st_size,'producedByJob':plan_id,'sourceFingerprint':payload['sourceFingerprint'],
                  'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':plan_id,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,
                'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedLibraryVerified':True,
                'affected':payload['affected'],'sourceModified':False,'designCacheUpdated':False,
                'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
                'verificationScope':'library_device_definitions','symbolGraphicsVerified':'expectedGraphDigest' in payload,
                'modeledLibraryPreservationVerified':'expectedGraphDigest' in payload,
                'notChecked':['dsn_cache','instance_connectivity','native_drc','rendered_symbol','other_library_properties','external_footprint']+([] if 'expectedGraphDigest' in payload else ['symbol_vector_graphics','reference_template'])}

    def open_output(self,plan_id,plan_digest):
        guard=self._guard()
        try:
            directory,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only verified library edit outputs may be opened.')
            self._verified_result(directory,row)
            with self.library.lock:
                if len(self.library.sessions)>=32:raise CadenceError('session_limit','Close a library session first.')
                internal=LibraryService(Config(self.config.install_root,self.config.workspace_root,(directory,),self.config.timeout_seconds))
                opened=internal.open(str(directory/'library.olb'));ident=opened['libraryId']
                self.library.sessions[ident]=internal.sessions.pop(ident)
                return opened|{'producedByPlan':plan_id,'outputKind':self.kind}
        finally:guard.close()
