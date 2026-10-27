"""Explicit endpoint edits/deletion; semantic target and full page pin oracles."""
from datetime import datetime,timezone
import copy,json,subprocess
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_wire import point,path_key,paths_valid,point_on_path,geometry_union,expected_definitions,inventory,connection_digest
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS


def edit_objects(objects,wire,operation,start,end,alias_moves,remove_aliases):
    attached=[o for o in objects if o['kind']=='alias' and o['attributes']['wireId']==wire['objectId']]
    if len(attached)>32:raise CadenceError('alias_limit','At most 32 attached aliases in this operation.')
    semantic=[(a['attributes']['name'],tuple(a['attributes']['location'])) for a in attached]
    if len(set(semantic))!=len(semantic):raise CadenceError('ambiguous_alias','Alias names/anchors do not uniquely identify native objects.')
    if operation=='delete':
        if alias_moves:raise CadenceError('invalid_alias_change','Deletion does not relocate aliases.')
        if attached and remove_aliases is not True:raise CadenceError('alias_removal_required','Explicitly acknowledge deletion of the attached aliases.')
        locations={a['objectId']:a['attributes']['location'] for a in attached}
    else:
        if remove_aliases:raise CadenceError('invalid_alias_change','Endpoint changes preserve aliases, not remove them.')
        if not isinstance(alias_moves,list) or any(not isinstance(a,dict) or set(a)!={'aliasId','location'} or not isinstance(a['aliasId'],str) or not point(a['location']) for a in alias_moves):raise CadenceError('invalid_alias_change','Provide explicit bounded alias anchors.')
        locations={a['aliasId']:a['location'] for a in alias_moves}
        if len(locations)!=len(alias_moves) or set(locations)!={a['objectId'] for a in attached}:raise CadenceError('incomplete_alias_expectations','Declare every attached alias once.')
        if any(not point_on_path(p,[start,end]) for p in locations.values()):raise CadenceError('invalid_alias_location','Every saved alias anchor must lie on the new segment.')
    expected=[]
    for obj in objects:
        row=copy.deepcopy(obj)
        if row['objectId']==wire['objectId']:
            if operation=='delete':continue
            row['attributes']['points']=[start,end]
        if row['kind']=='alias' and row['objectId'] in locations:
            if operation=='delete':continue
            row['attributes']['location']=locations[row['objectId']]
        expected.append(row)
    native_aliases=[{'name':a['attributes']['name'],'oldLocation':a['attributes']['location'],'location':locations[a['objectId']]} for a in attached]
    return expected,native_aliases


def unrelated_wire_nets(data,objects,page_id,excluded_net):
    schematics={s['objectId']:s['name'] for s in data['schematic']}
    pages={p['objectId']:(schematics[p['schematicId']],p['name']) for p in data['page']}
    return sorted([[*pages[o['pageId']],[list(p) for p in path_key(o['attributes']['points'])],o['attributes']['net']]
                   for o in objects if o['kind']=='wire' and not (o['pageId']==page_id and o['attributes']['net']==excluded_net)])

def verify_unrelated_wire_nets(data,objects,expected):
    actual=unrelated_wire_nets(data,objects,None,None)
    keys={(r[0],r[1],tuple(map(tuple,r[2]))) for r in expected}
    selected=[r for r in actual if (r[0],r[1],tuple(map(tuple,r[2]))) in keys]
    if selected!=expected:raise CadenceError('unrelated_wire_net_changed','Unrelated saved wire network identity differs from the frozen source.','verify')

class CaptureWireEdits(CapturePropertyEdits):
    kind='capture_wire_edit'
    def plan(self,sid,wire_id,operation,expectations,start=None,end=None,alias_moves=None,remove_aliases=False,expected_paths=None,expected_wire_net=None,gui_session_id=None,host_project=None,editor_occurrence=None):
        if (gui_session_id is None)!=(host_project is None):raise CadenceError('invalid_editor_host','Provide guiSessionId and hostProject together.')
        if gui_session_id is not None and operation!='delete':raise CadenceError('unsupported_editor_operation','The editor wire-edit backend currently accepts deletion; endpoint changes use the standalone backend.')
        if editor_occurrence is not None and (gui_session_id is None or not isinstance(editor_occurrence,str) or not 1<=len(editor_occurrence)<=512 or any(ord(c)<32 for c in editor_occurrence)):raise CadenceError('invalid_editor_occurrence','Use a bounded explicit occurrence reference with a GUI host.')
        if operation not in ('set_endpoints','delete'):raise CadenceError('invalid_wire_edit','Use set_endpoints or delete.')
        if operation=='set_endpoints':
            if not point(start) or not point(end) or start==end:raise CadenceError('invalid_wire_geometry','Two distinct bounded endpoints are required.')
        elif start is not None or end is not None or expected_wire_net is not None:raise CadenceError('invalid_wire_edit','Deletion does not specify new endpoints or wire net.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];objects=inventory(self.capture,sid)
            wire=next((o for o in objects if o['kind']=='wire' and o['objectId']==wire_id),None)
            if wire is None:raise CadenceError('object_not_found','Wire is outside this immutable session.')
            old=wire['attributes'];page_id=wire['pageId']
            if len(old['points'])!=2:raise CadenceError('unsupported_wire_shape','This endpoint operation requires a two-point scalar wire.')
            same=[o for o in objects if o['kind']=='wire' and o['pageId']==page_id and path_key(o['attributes']['points'])==path_key(old['points']) and o['attributes']['net']==old['net']]
            if len(same)!=1:raise CadenceError('ambiguous_wire','Coincident geometry/net targets require a more specific operation.')
            page=next(p for p in data['page'] if p['objectId']==page_id);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            expected_data=expected_definitions(data,page_id,expectations)
            changed,aliases=edit_objects(objects,wire,operation,start,end,[] if alias_moves is None else alias_moves,remove_aliases)
            if expected_paths is not None:
                wanted=[o['attributes']['points'] for o in changed if o['kind']=='wire' and o['pageId']==page_id]
                if not paths_valid(expected_paths) or geometry_union(expected_paths)!=geometry_union(wanted):raise CadenceError('invalid_wire_geometry','Declared saved paths must match the exact edited geometric union.')
                changed=[o for o in changed if not (o['kind']=='wire' and o['pageId']==page_id)]+[{'kind':'wire','pageId':page_id,'attributes':{'points':p}} for p in expected_paths]
            saved_paths=[o['attributes']['points'] for o in changed if o['kind']=='wire' and o['pageId']==page_id]
            owner=old['net'] if expected_wire_net is None else expected_wire_net
            if not isinstance(owner,str) or len(owner)>512 or '\x00' in owner:raise CadenceError('invalid_net_name','Invalid explicit wire net expectation.')
            for text in [old['net'],sch['name'],page['name'],*(a['name'] for a in aliases)]:
                if len(text)>512 or '\x00' in text:raise CadenceError('input_limit','Native locator exceeds its bounded literal argument size.')
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'schematicName':sch['name'],'pageName':page['name'],
                'wireId':wire_id,'operation':operation,'oldPoints':old['points'],'oldNet':old['net'],'start':start,'end':end,'aliases':aliases,
                'expectedWireNet':owner,'expectedConnections':expectations,'expectedWirePaths':saved_paths,'expectedDefinitionDigest':definition_baseline(expected_data),'expectedConnectionDigest':connection_digest(data,changed)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Wire edit plan exceeds durable record limit.')
            self.capture._session(sid)
            if operation=='delete':payload['expectedUnrelatedWireNets']=unrelated_wire_nets(data,objects,page_id,old['net'])
            if gui_session_id is not None:
                payload['editorHost']=self.editor_host.freeze(gui_session_id,host_project);payload['editorOccurrence']=editor_occurrence
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Wire-edit preservation proof exceeds the durable plan bound.')
            return self.create_plan(payload)
    def preview(self,p):
        result={k:p[k] for k in ('wireId','operation','schematicName','pageName','oldPoints','oldNet','start','end','aliases','expectedWireNet','expectedConnections','expectedWirePaths','sourceFingerprint')}
        result['unrelatedWireNetPreservationRequired']='expectedUnrelatedWireNets' in p
        if 'editorHost' in p:result.update(executionBackend='capture_editor',temporaryOutputProjectSwitch=True,hostProjectRestorationRequired=True,outputProjectClosureRequired=True,guiSessionReattachRequired=True,cancelScope='pending_only',editorOccurrence=p.get('editorOccurrence'))
        return result
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Wire source changed after planning.')
        if 'editorHost' in p:self.editor_host.static(p['editorHost'])
    def execute(self,directory,payload,cancel,on_started):
        if 'editorHost' in payload:return self.editor_host.execute(directory,payload,cancel,on_started)
        return super().execute(directory,payload,cancel,on_started)
    def cancel(self,plan_id,plan_digest):
        d,path,row=self._load(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
        if 'editorHost' in row['plan']['payload'] and row['state']=='started':raise CadenceError('too_late','A host delete task is pending-cancel only; observe/recover a started task.')
        return super().cancel(plan_id,plan_digest)
    def _verified_result(self,directory,row):
        result=super()._verified_result(directory,row)
        if 'editorHost' in row['plan']['payload']:self.editor_host.manifest(directory)
        return result
    def native_command(self,directory,p):
        new=p['oldPoints'] if p['operation']=='delete' else [p['start'],p['end']]
        args=[self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_wire.tcl',self.config.install_root,directory/'design.dsn',directory/'native-result.json',p['schematicName'],p['pageName'],p['operation'],*map(str,sum(p['oldPoints'],[])),p['oldNet'],*map(str,sum(new,[])),str(len(p['aliases']))]
        for alias in p['aliases']:args.extend([alias['name'],*map(str,alias['oldLocation']),*map(str,alias['location'])])
        if len(subprocess.list2cmdline(list(map(str,args))))>30000:raise CadenceError('argument_limit','Native edit argv exceeds bounded command length.')
        return args
    def verify(self,directory,p,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Wire edit output exceeds limit.')
        if 'editorHost' in p:
            from .gui_jobs import acquire_guard
            guard=acquire_guard(self.editor_host.binding(p['editorHost']).parent)
            try:self.editor_host.complete(directory,p['editorHost'])
            finally:guard.close()
        elif native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':p['operation'],'schematicName':p['schematicName'],'pageName':p['pageName']}:raise CadenceError('invalid_worker_result','Wire edit receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}};sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data'];objects=inventory(verifier,sid)
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('wire_edit_net_mismatch','Saved pin net bindings differ from the explicit edit plan.','verify')
            if connection_digest(data,objects)!=p['expectedConnectionDigest']:raise CadenceError('wire_edit_objects_mismatch','Saved wires/aliases/other connection objects differ from the plan.','verify')
            if 'expectedUnrelatedWireNets' in p:verify_unrelated_wire_nets(data,objects,p['expectedUnrelatedWireNets'])
            wires={o['objectId']:o for o in objects if o['kind']=='wire'}
            for alias in (o for o in objects if o['kind']=='alias'):
                if not point_on_path(alias['attributes']['location'],wires[alias['attributes']['wireId']]['attributes']['points']):raise CadenceError('invalid_alias_attachment','Saved alias is off its owning wire.','verify')
            if p['operation']=='set_endpoints':
                sch={s['objectId']:s['name'] for s in data['schematic']};pages={r['objectId'] for r in data['page'] if r['name']==p['pageName'] and sch[r['schematicId']]==p['schematicName']}
                candidates=[o for o in wires.values() if o['pageId'] in pages and path_key(o['attributes']['points'])==path_key([p['start'],p['end']])]
                if len(candidates)!=1 or candidates[0]['attributes']['net']!=p['expectedWireNet']:raise CadenceError('wire_edit_owner_net_mismatch','Edited wire native net name differs from the explicit expectation.','verify')
        finally:verifier.close(sid)
        if sha256(target)!=before:raise CadenceError('target_changed','Wire output changed during verification.')
        self.preflight(p);ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'wire-edit-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        result={'planId':ident,'state':'verified' if native_completed else 'verified_recovered','operation':p['operation'],'artifact':artifact,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedDefinitionsVerified':True,'expectedConnectionObjectsVerified':True,'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['occurrence_connectivity','junction_flags','wire_only_net_identity','native_drc','rendered_layout','other_part_properties']}

        result['unrelatedWireNetIdentityPreserved']='expectedUnrelatedWireNets' in p
        if 'editorHost' in p:
            self.editor_host.manifest(directory,create=True)
            result.update(executionBackend='capture_editor',hostContextPreserved=True,guiSessionReattachRequired=True,outputProjectCloseVerified=True)
        return result
