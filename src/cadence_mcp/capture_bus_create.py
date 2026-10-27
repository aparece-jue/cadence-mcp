"""Persistent simple-bus creation with declared geometry and native entry expectations."""
import copy,json,re
from datetime import datetime,timezone
from .core import CadenceError,checked_path,sha256
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_wire import inventory,expected_definitions,connection_digest,geometry_union,point,point_on_path
from .capture_bus import query_bus
from .editor_wire_host import EditorWireHost,ADAPTER_NAMES
from .isolated_jobs import digest
from .gui_jobs import acquire_guard

def validate_spec(prefix,first,last,start,end,branches):
    if not isinstance(prefix,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',prefix):raise CadenceError('invalid_bus_spec','Use a literal bounded bus prefix.')
    if any(type(v) is not int or not 0<=v<=65535 for v in (first,last)) or not 2<=abs(first-last)+1<=128:raise CadenceError('invalid_bus_spec','Use a contiguous range of2..128 nonnegative indices.')
    if not point(start) or not point(end) or start==end or start[0]!=end[0]:raise CadenceError('unsupported_bus_geometry','This creation backend accepts a vertical bus with distinct bounded endpoints.')
    if not isinstance(branches,list) or len(branches)>abs(first-last)+1:raise CadenceError('invalid_bus_spec','Declare at most one branch per member.')
    seen=set();anchors=set();ends=set();indices=list(range(first,last+(1 if last>first else -1),1 if last>first else -1))
    for b in branches:
        if not isinstance(b,dict) or set(b)!={'index','entryPoint','endPoint','wireEnd','expectedBusAttached'}:raise CadenceError('invalid_bus_branch','Invalid typed branch fields.')
        if type(b['index']) is not int or b['index'] not in indices or b['index'] in seen or type(b['expectedBusAttached']) is not bool:raise CadenceError('invalid_bus_branch','Unknown/duplicate member or nonboolean attachment expectation.')
        if not all(point(b[k]) for k in ('entryPoint','endPoint','wireEnd')) or b['entryPoint']==b['endPoint'] or b['endPoint']==b['wireEnd']:raise CadenceError('invalid_bus_geometry','Entry and scalar endpoints must be bounded and distinct.')
        if b['endPoint'][0]!=b['wireEnd'][0] and b['endPoint'][1]!=b['wireEnd'][1]:raise CadenceError('unsupported_bus_geometry','Scalar branches currently require an orthogonal segment.')
        if point_on_path(b['entryPoint'],[start,end])!=b['expectedBusAttached']:raise CadenceError('inconsistent_bus_expectation','Declare on-bus attachment or explicit off-bus placement consistently; native links are still independently verified.')
        if tuple(b['entryPoint']) in anchors or tuple(b['endPoint']) in ends:raise CadenceError('entry_collision','New entry anchors/endpoints must be unique.')
        seen.add(b['index']);anchors.add(tuple(b['entryPoint']));ends.add(tuple(b['endPoint']))
    return {'prefix':prefix,'first':first,'last':last,'busName':f'{prefix}[{first}..{last}]','start':start,'end':end,'branches':copy.deepcopy(branches),'members':[prefix+str(i) for i in indices]}

def _scopes(data):
    sch={s['objectId']:s['name'] for s in data['schematic']}
    return {p['objectId']:[sch[p['schematicId']],p['name']] for p in data['page']}

def _wire_meta(w):return [w['isBus'],w['isBundle'],w['name'],w['width'],[m['name'] for m in w['members']]]

def wire_groups(data,wires):
    scopes=_scopes(data);groups={}
    for w in wires:
        key=json.dumps([scopes[w['pageId']],_wire_meta(w)],sort_keys=True)
        groups.setdefault(key,[]).append(w['points'])
    return [[json.loads(key),geometry_union(paths)] for key,paths in sorted(groups.items())]

def entry_rows(data,buses):
    scopes=_scopes(data);wires={w['wireId']:w for w in buses['wires']};rows=[]
    for e in buses['entries']:
        rows.append([scopes[e['pageId']],e['entryPoint'],e['endPoint'],None if e['entryWireId'] is None else _wire_meta(wires[e['entryWireId']]),None if e['endWireId'] is None else _wire_meta(wires[e['endWireId']])])
    return sorted(rows,key=lambda x:json.dumps(x,sort_keys=True))

class EditorBusHost(EditorWireHost):
    adapter_names=ADAPTER_NAMES+('editor_bus_create_job.tcl',)
    def invocation(self,d,p,project,target,owner):
        h=p['editorHost'];s=p['spec']
        args=[h['pid'],h['activeDesign'],h['hostProject'],project.as_posix(),target.as_posix(),p['schematicName'],p['pageName'],p.get('editorOccurrence') or '',*s['start'],*s['end'],s['busName'],*s['start'],(d/'native-result.json').as_posix(),(d/'entered.txt').as_posix(),owner['jobId'],json.dumps(s,ensure_ascii=False)]
        return 'editor_bus_create_job.tcl','::cmcpEditorBus::run',args

class CaptureBusCreates(CapturePropertyEdits):
    kind='capture_bus_create'
    def __init__(self,config,capture,gui):super().__init__(config,capture);self.editor_host=EditorBusHost(config,gui)

    def plan(self,sid,gui_sid,host_project,page_id,prefix,first,last,start,end,branches,expectations,editor_occurrence=None):
        spec=validate_spec(prefix,first,last,start,end,branches)
        if editor_occurrence is not None and (not isinstance(editor_occurrence,str) or not 1<=len(editor_occurrence)<=512 or any(ord(c)<32 for c in editor_occurrence)):raise CadenceError('invalid_editor_occurrence','Use a bounded literal occurrence reference.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];pages=[p for p in data['page'] if p['objectId']==page_id]
            if len(pages)!=1:raise CadenceError('object_not_found','Page is outside this session.')
            page=pages[0];sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['schematicId']==page['schematicId'] and p['name']==page['name'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic identity must be unique.')
            expected=expected_definitions(data,page_id,expectations);objects=inventory(self.capture,sid);query_bus(self.capture,sid,'bus',limit=1);before=session['busInventory']
            if any(w['isBundle'] for w in before['wires']):raise CadenceError('unsupported_bundle_preservation','Create ordinary buses in a source without unverified Bundle state.')
            new_names={spec['busName'],*spec['members']}
            if any(w['pageId']==page_id and w['name'] in new_names for w in before['wires']) or any(o['pageId']==page_id and o['kind']=='alias' and o['attributes']['name'] in new_names for o in objects):raise CadenceError('bus_name_conflict','A target-page bus/member name already exists; implicit net retargeting is unsupported.')
            existing_anchors={tuple(e['entryPoint']) for e in before['entries'] if e['pageId']==page_id};existing_ends={tuple(e['endPoint']) for e in before['entries'] if e['pageId']==page_id}
            if any(tuple(b['entryPoint']) in existing_anchors or tuple(b['endPoint']) in existing_ends for b in branches):raise CadenceError('entry_collision','New and existing entries overlap.')
            new_bus={'pageId':page_id,'isBus':True,'isBundle':False,'name':spec['busName'],'points':[start,end],'width':len(spec['members']),'members':[{'position':i,'name':name} for i,name in enumerate(spec['members'])]}
            wanted_wires=copy.deepcopy(before['wires'])+[new_bus];wanted_entries=entry_rows(data,before);wanted_other=[copy.deepcopy(o) for o in objects if o['kind']!='wire']
            def alias(name,location):return {'kind':'alias','pageId':page_id,'attributes':{'wireId':'new','name':name,'location':location}}
            wanted_other.append(alias(spec['busName'],start));scope=_scopes(data)[page_id]
            for b in branches:
                name=prefix+str(b['index']);wire={'pageId':page_id,'isBus':False,'isBundle':False,'name':name,'points':[b['endPoint'],b['wireEnd']],'width':0,'members':[]};wanted_wires.append(wire);wanted_other.append(alias(name,b['wireEnd']))
                wanted_entries.append([scope,b['entryPoint'],b['endPoint'],_wire_meta(new_bus) if b['expectedBusAttached'] else None,_wire_meta(wire)])
            wanted_entries.sort(key=lambda x:json.dumps(x,sort_keys=True))
            payload={'operation':'bus_create','sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'schematicName':sch['name'],'pageName':page['name'],'spec':spec,'expectedConnections':expectations,'expectedDefinitionDigest':definition_baseline(expected),'expectedWireGroupsDigest':digest(wire_groups(data,wanted_wires)),'expectedOtherConnectionsDigest':connection_digest(data,wanted_other),'expectedEntriesDigest':digest(wanted_entries),'editorOccurrence':editor_occurrence,'editorHost':self.editor_host.freeze(gui_sid,host_project)}
            if len(json.dumps(payload,ensure_ascii=True).encode('utf-8'))>48000:raise CadenceError('plan_limit','Bus plan exceeds the durable record bound.')
            self.preflight(payload);return self.create_plan(payload)

    def preview(self,p):return {'schematicName':p['schematicName'],'pageName':p['pageName'],'busName':p['spec']['busName'],'members':p['spec']['members'],'branches':p['spec']['branches'],'expectedConnections':p['expectedConnections'],'sourceFingerprint':p['sourceFingerprint'],'temporaryOutputProjectSwitch':True,'hostProjectRestorationRequired':True,'guiSessionReattachRequired':True,'cancelScope':'pending_only','designPassed':None}

    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if source.suffix.lower()!='.dsn' or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Frozen bus source changed.')
        s=p['spec'];validated=validate_spec(s['prefix'],s['first'],s['last'],s['start'],s['end'],s['branches'])
        if validated!=s or p['operation']!='bus_create':raise CadenceError('invalid_plan','Bus specification differs from its typed form.')
        self.editor_host.static(p['editorHost'])

    def execute(self,d,p,cancel,on_started):return self.editor_host.execute(d,p,cancel,on_started)

    def cancel(self,plan_id,plan_digest):
        d,path,row=self._load(plan_id)
        if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
        if row['state']=='started':raise CadenceError('too_late','A started host task is observe/recover only; never kill Capture.')
        return super().cancel(plan_id,plan_digest)

    def verify(self,d,p,native_completed):
        guard=acquire_guard(self.editor_host.binding(p['editorHost']).parent)
        try:self.editor_host.complete(d,p['editorHost'])
        finally:guard.close()
        target=checked_path(str(d/'design.dsn'),(d,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Bus output exceeds the size bound.')
        v=CaptureService(self.config);v.workspaces['output']={'directory':d,'manifest':{'copiedFingerprint':before}};sid=v.open('output')['sessionId']
        try:
            data=v.sessions[sid]['data'];objects=inventory(v,sid);query_bus(v,sid,'bus',limit=1);buses=v.sessions[sid]['busInventory']
            if definition_baseline(data)!=p['expectedDefinitionDigest']:raise CadenceError('bus_pin_mismatch','Saved definition pin connections differ from explicit expectations.','verify')
            if digest(wire_groups(data,buses['wires']))!=p['expectedWireGroupsDigest']:raise CadenceError('bus_wire_mismatch','Saved named wire groups/member order/geometry differ from the plan.','verify')
            if connection_digest(data,[o for o in objects if o['kind']!='wire'])!=p['expectedOtherConnectionsDigest']:raise CadenceError('bus_object_mismatch','Saved aliases or other connection objects differ.','verify')
            if digest(entry_rows(data,buses))!=p['expectedEntriesDigest']:raise CadenceError('bus_entry_mismatch','Saved entry endpoints or native wire references differ.','verify')
            wires={w['wireId']:w for w in buses['wires']}
            for e in buses['entries']:
                for key,coordinate in [('entryWireId','entryPoint'),('endWireId','endPoint')]:
                    if e[key] is not None and not point_on_path(e[coordinate],wires[e[key]]['points']):raise CadenceError('bus_entry_geometry_link_mismatch','Native entry wire reference does not contain its endpoint.','verify')
            connection_wires={o['objectId']:o for o in objects if o['kind']=='wire'}
            for a in (o for o in objects if o['kind']=='alias'):
                if not point_on_path(a['attributes']['location'],connection_wires[a['attributes']['wireId']]['attributes']['points']):raise CadenceError('bus_alias_attachment_mismatch','Alias is off its native owner wire.','verify')
        finally:v.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Bus output changed during verification.')
        self.editor_host.manifest(d,create=True);ident=d.name.removeprefix('plan-');s=p['spec'];routing_complete=len(s['branches'])==len(s['members']) and all(b['expectedBusAttached'] for b in s['branches'])
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':{'artifactId':'bus-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'},'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),'busName':s['busName'],'memberCount':len(s['members']),'declaredBranchCount':len(s['branches']),'localEntryRoutingComplete':routing_complete,'routingScope':'local_bus_entry_structure','expectedDefinitionsVerified':True,'expectedNamedWireGeometryVerified':True,'expectedNativeEntryLinksVerified':True,'sourceModified':False,'hostContextPreserved':True,'outputProjectCloseVerified':True,'guiSessionReattachRequired':True,'nativeCompletionVerified':native_completed,'designPassed':None,'notChecked':['physical_pin_member_connectivity','occurrence_bus_connectivity','nested_bundle_semantics','other_part_properties','native_drc','rendered_layout']}

    def _verified_result(self,d,row):
        result=super()._verified_result(d,row);self.editor_host.manifest(d);return result
