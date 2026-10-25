"""Planned scalar wire/alias addition with explicit page pin and geometry oracles."""
from datetime import datetime,timezone
from math import gcd
import copy,json,re
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_objects import query_objects
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS
from .isolated_jobs import digest


def point(value):
    return isinstance(value,list) and len(value)==2 and all(type(v) is int and abs(v)<=1000000 for v in value)


def paths_valid(paths):
    return (isinstance(paths,list) and len(paths)<=500 and sum(len(p) for p in paths if isinstance(p,list))<=10000
            and all(isinstance(p,list) and 2<=len(p)<=1000 and all(point(v) for v in p)
                    and all(a!=b for a,b in zip(p,p[1:])) for p in paths))


def path_key(path):return min(tuple(map(tuple,path)),tuple(map(tuple,reversed(path))))


def geometry_union(paths):
    """Exact integer segment union: declared splitting preserves wire geometry."""
    lines={}
    for path in paths:
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];scale=gcd(abs(dx),abs(dy))
            if not scale:raise CadenceError('invalid_wire_geometry','Zero-length wire segment.')
            ux,uy=dx//scale,dy//scale
            if ux<0 or (ux==0 and uy<0):ux,uy=-ux,-uy
            key=(ux,uy,ux*a[1]-uy*a[0])
            lo,hi=sorted((ux*a[0]+uy*a[1],ux*b[0]+uy*b[1]))
            lines.setdefault(key,[]).append((lo,hi))
    result=[]
    for key,intervals in sorted(lines.items()):
        merged=[]
        for lo,hi in sorted(intervals):
            if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
            else:merged.append((lo,hi))
        result.append((key,merged))
    return result


def point_on_path(location,path):
    x,y=location
    return any((b[0]-a[0])*(y-a[1])==(b[1]-a[1])*(x-a[0])
               and min(a[0],b[0])<=x<=max(a[0],b[0]) and min(a[1],b[1])<=y<=max(a[1],b[1]) for a,b in zip(path,path[1:]))


def inventory(capture,sid):
    query_objects(capture,sid,'connections','wire',None,None,1)
    return capture._session(sid)['objectInventories']['connections']


def connection_digest(data,objects,replacement=None):
    """Stable semantic locations, not ordinal/native identifiers across save/reopen."""
    sch={r['objectId']:r['name'] for r in data['schematic']}
    pages={r['objectId']:(sch[r['schematicId']],r['name']) for r in data['page']}
    rows=[]
    for obj in objects:
        kind=obj['kind'];scope=pages[obj['pageId']];attrs=copy.deepcopy(obj['attributes'])
        if replacement and obj['pageId']==replacement['pageId'] and kind=='wire':continue
        if kind=='wire':attrs={'points':path_key(attrs['points'])}
        elif kind=='alias':attrs.pop('wireId')
        elif kind=='nc':attrs.pop('partId');attrs.pop('pinId')
        rows.append([kind,scope,attrs])
    if replacement:
        scope=pages[replacement['pageId']]
        rows.extend(['wire',scope,{'points':path_key(p)}] for p in replacement['paths'])
        rows.append(['alias',scope,{'name':replacement['name'],'location':replacement['location']}])
    return digest(sorted(rows,key=lambda row:json.dumps(row,sort_keys=True)))


def expected_definitions(data,page_id,expectations):
    if not isinstance(expectations,list) or len(expectations)>500:raise CadenceError('invalid_expectations','Provide up to 500 explicit page pin expectations.')
    sch={s['objectId']:s['name'] for s in data['schematic']};pages={p['objectId']:p for p in data['page']}
    page=pages[page_id];pins=[p for p in data['pin'] if p['pageId']==page_id]
    index={}
    for pin in pins:index.setdefault((pin['reference'],pin['number']),[]).append(pin)
    if any(len(v)!=1 for v in index.values()):raise CadenceError('ambiguous_pin_scope','Shared or repeated page pin identities need a unit-aware operation.')
    supplied={};expected=copy.deepcopy(data)
    for row in expectations:
        if (not isinstance(row,dict) or set(row)!={'schematicName','pageName','reference','pinNumber','connected','net'}
            or type(row['connected']) is not bool or any(not isinstance(row[k],str) for k in ('schematicName','pageName','reference','pinNumber'))):
            raise CadenceError('invalid_expectations','Invalid typed pin expectation.')
        if row['schematicName']!=sch[page['schematicId']] or row['pageName']!=page['name']:
            raise CadenceError('invalid_expectations','Every expected pin must belong to the selected page.')
        key=(row['reference'],row['pinNumber'])
        if key in supplied or key not in index:raise CadenceError('invalid_expectations','Unknown or duplicate expected pin.')
        if row['connected']:
            if not isinstance(row['net'],str) or not row['net'] or len(row['net'])>512:raise CadenceError('invalid_expectations','Connected pins require explicit net names.')
        elif row['net'] is not None:raise CadenceError('invalid_expectations','An unbound pin expects null net.')
        supplied[key]=row
    if supplied.keys()!=index.keys():raise CadenceError('incomplete_expectations','Explicit expectations must cover every existing pin on the selected page.')
    for pin in expected['pin']:
        if pin['pageId']==page_id:
            row=supplied[(pin['reference'],pin['number'])];pin.update(connected=row['connected'],net=row['net'] or '')
    return expected


class CaptureWireAdds(CapturePropertyEdits):
    kind='capture_wire_add'

    def plan(self,session_id,page_id,start,end,name,expectations,alias_location=None,expected_paths=None,expected_wire_net=None):
        if not point(start) or not point(end) or start==end:raise CadenceError('invalid_wire_geometry','Two distinct bounded integer endpoints are required.')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}',name):raise CadenceError('invalid_net_name','Provide a bounded scalar alias identifier; bus expressions require a dedicated operation.')
        owner_net=name if expected_wire_net is None else expected_wire_net
        if not isinstance(owner_net,str) or not 1<=len(owner_net)<=512 or any(ord(c)<32 for c in owner_net):
            raise CadenceError('invalid_net_name','Expected alias-owner wire net must be an explicit bounded name.')
        location=start if alias_location is None else alias_location
        if not point(location) or not point_on_path(location,[start,end]):raise CadenceError('invalid_alias_location','Alias anchor must lie on the requested new segment.')
        with self.capture.lock:
            session=self.capture._session(session_id);data=session['data']
            page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('object_not_found','Page is outside this immutable session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['schematicId']==page['schematicId'] and p['name']==page['name'] for p in data['page'])!=1:
                raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            expected=expected_definitions(data,page_id,expectations)
            objects=inventory(self.capture,session_id)
            prior=[o['attributes']['points'] for o in objects if o['kind']=='wire' and o['pageId']==page_id]
            if any(o['kind']=='alias' and o['pageId']==page_id and o['attributes']['name']==name and o['attributes']['location']==location for o in objects):
                raise CadenceError('alias_exists','An identical alias anchor already exists on the page.')
            paths=copy.deepcopy(prior+[[start,end]] if expected_paths is None else expected_paths)
            if not paths_valid(paths) or geometry_union(paths)!=geometry_union(prior+[[start,end]]):
                raise CadenceError('invalid_wire_geometry','Expected saved paths must cover exactly the existing geometry plus the requested new segment.')
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],
                'schematicName':sch['name'],'pageName':page['name'],'start':start,'end':end,'netName':name,'aliasLocation':location,'expectedWireNet':owner_net,
                'expectedConnections':expectations,'expectedWirePaths':paths,'expectedDefinitionDigest':definition_baseline(expected),
                'expectedConnectionDigest':connection_digest(data,objects,{'pageId':page_id,'paths':paths,'name':name,'location':location})}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Wire plan exceeds the bounded durable-record size.')
            self.capture._session(session_id)
            return self.create_plan(payload)

    def preview(self,payload):return {k:payload[k] for k in ('schematicName','pageName','start','end','netName','aliasLocation','expectedWireNet','expectedConnections','expectedWirePaths','sourceFingerprint')}

    def preflight(self,payload):
        source=checked_path(payload['sourceDesign'],(self.config.workspace_root,))
        if source.suffix.lower()!='.dsn' or sha256(source)!=payload['sourceFingerprint']:raise CadenceError('target_changed','Source snapshot changed after wire planning.')

    def native_command(self,directory,payload):
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_wire_add.tcl',self.config.install_root,
            directory/'design.dsn',directory/'native-result.json',payload['schematicName'],payload['pageName'],
            *map(str,payload['start']),*map(str,payload['end']),payload['netName'],*map(str,payload['aliasLocation'])]

    def verify(self,directory,payload,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Wire output exceeds design limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'add_wire','schematicName':payload['schematicName'],'pageName':payload['pageName']}:
                raise CadenceError('invalid_worker_result','Native wire save receipt mismatch.','verify')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=payload['expectedDefinitionDigest']:raise CadenceError('unexpected_connectivity_change','Saved pin definitions/net bindings differ from the explicit plan.','verify')
            objects=inventory(verifier,sid)
            if connection_digest(data,objects)!=payload['expectedConnectionDigest']:raise CadenceError('unexpected_wire_geometry','Saved wire paths/aliases or other connection objects differ from the explicit plan.','verify')
            wires={o['objectId']:o for o in objects if o['kind']=='wire'}
            for alias in (o for o in objects if o['kind']=='alias'):
                if not point_on_path(alias['attributes']['location'],wires[alias['attributes']['wireId']]['attributes']['points']):
                    raise CadenceError('invalid_alias_attachment','Saved alias anchor is not on its owning wire.','verify')
            sch={s['objectId']:s['name'] for s in data['schematic']}
            page_ids={p['objectId'] for p in data['page'] if p['name']==payload['pageName'] and sch[p['schematicId']]==payload['schematicName']}
            added=[o for o in objects if o['kind']=='alias' and o['pageId'] in page_ids
                   and o['attributes']['name']==payload['netName'] and o['attributes']['location']==payload['aliasLocation']]
            if len(added)!=1:raise CadenceError('ambiguous_alias','New alias identity is not unique after save.','verify')
            owner_net=wires[added[0]['attributes']['wireId']]['attributes']['net']
            if owner_net!=payload.get('expectedWireNet',payload['netName']):
                raise CadenceError('unexpected_alias_owner_net','New alias owner wire net differs from the explicit expectation.','verify')
        finally:verifier.close(sid)
        if sha256(target)!=before:raise CadenceError('target_changed','Output changed during wire verification.')
        self.preflight(payload)
        ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'wire-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,
            'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':payload['sourceFingerprint'],
            'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,
            'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedDefinitionsVerified':True,
            'expectedConnectionObjectsVerified':True,'expectedConnections':payload['expectedConnections'],'sourceModified':False,
            'addedAliasOwnerNetVerified':True,'observedAliasOwnerNet':owner_net,'wireOnlyNetIdentityVerified':False,
            'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
            'notChecked':['occurrence_connectivity','wire_only_net_identity','native_drc','rendered_layout','font_descriptor','other_part_properties']}
