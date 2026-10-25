"""Bound existing OLB vector edits with complete modeled library preservation."""
import copy,json,shutil
from datetime import datetime,timezone
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,process_env,run_tcl
from .process_tree import run_owned_process
from .embedded_tcl import command as embedded_command
from .isolated_jobs import digest
from .library import validate_library
from .library_edit import LibraryPinEdits
from .library_semantics import library_graph
from .library_vectors import validate_vectors,vector_descriptor,BitmapGeometry
from .library_vector_query import query_library_vectors,validate_descriptor

def sortrows(rows):return sorted(rows,key=lambda r:json.dumps(r,ensure_ascii=False,sort_keys=True))

def vector_graph(data):
    """Keep native text classification for all untouched objects, unlike creation expectations."""
    try:
        base={k:v for k,v in data.items() if k!='meta'};validate_library(base)
        definitions=library_graph(base);meta=data['meta']
        if set(meta)!={'packages','symbols'}:raise ValueError('Metadata shape')
        packages={r['objectId']:r for r in base['package']}
        devices={r['objectId']:r for r in base['device']};cells={r['objectId']:r for r in base['cell']}
        scopes={}
        for part in base['part']:
            device=devices[part['deviceId']]
            scope=[packages[part['packageId']]['name'],device['designator'],device['position'],cells[part['cellId']]['name'],part['name']]
            scopes[tuple(scope)]={p['position'] for p in base['pin'] if p['partId']==part['objectId']}
        rows=[];seen=set()
        for row in meta['symbols']:
            if set(row)!={'scope','pinStarts','lines','otherVectorTypes','orderedVectors'} or row['otherVectorTypes']:raise ValueError('Unknown/unordered vectors')
            scope=tuple(row['scope'])
            if scope not in scopes or scope in seen:raise ValueError('Invalid vector scope')
            seen.add(scope)
            pins=row['pinStarts']
            if not isinstance(pins,list) or len(pins)!=len(scopes[scope]):raise ValueError('Pin starts')
            if any(set(p)!={'position','start'} or type(p['position']) is not int or not isinstance(p['start'],list) or len(p['start'])!=2
                   or any(type(c) is not int for c in p['start']) for p in pins):raise ValueError('Invalid pin starts')
            if {p['position'] for p in pins}!=scopes[scope]:raise ValueError('Incomplete pin starts')
            vectors=row['orderedVectors']
            if not isinstance(vectors,list) or len(vectors)>4096:raise ValueError('Vector count')
            for v in vectors:validate_descriptor(v)
            if sum(len(v[1]) for v in vectors if v[0] in ('polygon','polyline','bezier'))>65536:raise ValueError('Point budget')
            if sum(len(v[1]) for v in vectors if v[0]=='text')>262144:raise ValueError('Text budget')
            rows.append({'scope':list(scope),'pinStarts':sortrows(pins),'orderedVectors':copy.deepcopy(vectors)})
        if seen!=set(scopes):raise ValueError('Missing metadata scopes')
        templates=meta['packages']
        if not isinstance(templates,list) or len(templates)!=len(packages):raise ValueError('Package templates')
        if any(set(p)!={'packageName','referenceTemplate'} or not isinstance(p['packageName'],str) or not isinstance(p['referenceTemplate'],str) for p in templates):raise ValueError('Template fields')
        if sorted(p['packageName'] for p in templates)!=sorted(p['name'] for p in base['package']):raise ValueError('Template ownership')
        return {'definitions':definitions,'metadata':{'packages':sortrows(templates),'symbols':sorted(rows,key=lambda r:json.dumps(r['scope'],ensure_ascii=False))}}
    except (ValueError,TypeError,KeyError) as error:
        raise CadenceError('invalid_library_vector_graph','A complete unambiguous basic-vector library snapshot is required.') from error

def normalize_target_font(graph,part_name,index,operation,new_kind):
    result=copy.deepcopy(graph)
    if operation=='update' and new_kind=='text':
        for row in result['metadata']['symbols']:
            if row['scope'][-1]==part_name:
                if index>=len(row['orderedVectors']):raise CadenceError('library_vector_mismatch','Updated target vector is missing.')
                vector=row['orderedVectors'][index]
                if vector[0]!='text' or len(vector)!=6:raise CadenceError('library_vector_mismatch','Updated text descriptor is malformed.')
                vector.pop() # IsFontDefault is derived only for the explicitly updated text.
    return result

def expected_vector_edit(graph,scope,index,operation,replacement,bitmap_geometry=None):
    if operation not in ('update','delete') or type(index) is not int or index<0:raise CadenceError('invalid_vector_edit','Specify update/delete and a bound vector.')
    matches=[r for r in graph['metadata']['symbols'] if r['scope']==scope]
    if len(matches)!=1 or index>=len(matches[0]['orderedVectors']):raise CadenceError('object_not_found','Vector is outside the selected library part.')
    target=matches[0];old=target['orderedVectors'][index]
    if operation=='delete':
        if replacement is not None or bitmap_geometry is not None:raise CadenceError('invalid_vector_edit','Delete has no replacement or geometry declaration.')
        declaration=None;new=None
    elif old[0]=='bitmap':
        if replacement is not None or bitmap_geometry is None:raise CadenceError('invalid_bitmap_edit','Bitmap update requires only bitmapGeometry; pixel replacement is unavailable.')
        try:geometry=BitmapGeometry.model_validate(bitmap_geometry,strict=True).model_dump()
        except ValueError as error:raise CadenceError('invalid_bitmap_edit','Invalid explicit bitmap geometry or DIB digest.') from error
        if geometry['expectedDibSha256']!=old[5]:raise CadenceError('bitmap_content_mismatch','Expected bitmap pixels differ from the bound snapshot.')
        declaration={'kind':'bitmap','bounds':geometry['bounds'],'location':geometry['location']}
        new=['bitmap',geometry['bounds'],geometry['location'],*copy.deepcopy(old[3:])]
        if new==old:raise CadenceError('no_change','Bitmap geometry already matches the declaration.')
    else:
        if bitmap_geometry is not None:raise CadenceError('invalid_bitmap_edit','Bitmap geometry requires a bitmap target.')
        declaration=validate_vectors([replacement])[0];new=vector_descriptor(declaration)
        if declaration['kind']!=old[0]:raise CadenceError('vector_kind_change','Update retains the native vector kind and draw position.')
        old_fields=old[:-1] if old[0]=='text' else old
        if new==old_fields:raise CadenceError('no_change','Vector fields already match the requested declaration.')
        if new[0]=='text':new.append(old[-1])
    expected=copy.deepcopy(graph);affected=[]
    for row in expected['metadata']['symbols']:
        if row['scope'][-1].casefold()==scope[-1].casefold() and row['scope'][-1]!=scope[-1]:
            raise CadenceError('ambiguous_library_graph','Case-alias symbol names cannot be safely edited.')
        if row['scope'][-1]!=scope[-1]:continue
        if row['orderedVectors']!=target['orderedVectors'] or row['pinStarts']!=target['pinStarts']:
            raise CadenceError('ambiguous_library_graph','Repeated part names must resolve to the same complete native symbol view.')
        affected.append(row['scope'])
        if operation=='delete':row['orderedVectors'].pop(index)
        else:row['orderedVectors'][index]=copy.deepcopy(new)
    return expected,declaration,copy.deepcopy(old),affected

class LibraryVectorEdits(LibraryPinEdits):
    kind='library_vector'
    # Payload <=48KB; result repeats affected scopes, plus process/recovery metadata.
    # Keep that terminal record readable without enlarging other operation families.
    max_record_bytes=128*1024
    def _read_graph(self,source,directory):
        output=directory/(new_id('library-vector-graph')+'.json')
        run_tcl(self.config,'inspect_library_create.tcl',[str(source),str(output),'100000','1'],directory)
        if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Library vector graph exceeds32MiB.')
        try:return vector_graph(json.loads(output.read_text(encoding='utf-8'))),output
        except (ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_worker_result','Invalid library vector graph.') from error

    def plan(self,library_id,part_id,vector_id,operation,replacement=None,bitmap_geometry=None):
        with self.library.lock:
            session=self.library._session(library_id);data=session['data']
            vectors=query_library_vectors(self.library,library_id,part_id,None,1000)
            rows=list(vectors['items'])
            while vectors['nextCursor']:
                vectors=query_library_vectors(self.library,library_id,part_id,vectors['nextCursor'],1000);rows.extend(vectors['items'])
            targets=[r for r in rows if r['objectId']==vector_id]
            if len(targets)!=1:raise CadenceError('object_not_found','Vector does not belong to the selected part/revision.')
            target=targets[0];part=next(r for r in data['part'] if r['objectId']==part_id)
            package=next(r for r in data['package'] if r['objectId']==part['packageId']);device=next(r for r in data['device'] if r['objectId']==part['deviceId']);cell=next(r for r in data['cell'] if r['objectId']==part['cellId'])
            scope=[package['name'],device['designator'],device['position'],cell['name'],part['name']]
            source=session['directory']/'library.olb';before,before_file=self._read_graph(source,session['directory'])
            if before['definitions']!=library_graph(data):raise CadenceError('target_changed','Library definitions differ from the bound snapshot.')
            expected,declaration,old,affected=expected_vector_edit(before,scope,target['index'],operation,replacement,bitmap_geometry)
            if old!=target['descriptor']:raise CadenceError('target_changed','Target vector differs from the query snapshot.')
            comparable=normalize_target_font(expected,part['name'],target['index'],operation,declaration['kind'] if declaration else None)
            expected_file=session['directory']/(new_id('expected-vector-edit')+'.json');write_json(expected_file,comparable)
            self.library._session(library_id)
            payload={'sourceLibrary':str(source),'sourceFingerprint':session['revision'],'partId':part_id,'vectorId':vector_id,
              'scope':scope,'index':target['index'],'old':old,'operation':operation,'replacement':declaration,'affectedScopes':affected,
              'beforeGraphDigest':digest(before),'expectedGraphDigest':digest(comparable),
              'beforeEvidence':str(before_file),'beforeEvidenceHash':sha256(before_file),
              'expectedEvidence':str(expected_file),'expectedEvidenceHash':sha256(expected_file)}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Vector edit plan exceeds the bounded durable record.')
            return self.create_plan(payload)

    def preview(self,p):return {k:p[k] for k in ('partId','vectorId','scope','index','old','operation','replacement','affectedScopes','sourceFingerprint')}
    def preflight(self,p):
        source=checked_path(p['sourceLibrary'],(self.config.workspace_root,))
        if source.suffix.lower()!='.olb' or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Library source changed after planning.')
        for name in ('beforeEvidence','expectedEvidence'):
            evidence=checked_path(p[name],(self.config.workspace_root,))
            if sha256(evidence)!=p[name+'Hash']:raise CadenceError('target_changed','Frozen vector edit evidence changed.')
    def native_command(self,d,p):return embedded_command(self.config.install_root,'edit_library_vector.tcl',[d/'library.olb',d/'vector-edit.json',d/'native-result.json'])
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);source=checked_path(p['sourceLibrary'],(self.config.workspace_root,));target=d/'library.olb'
        with source.open('rb') as original,target.open('xb') as copied:shutil.copyfileobj(original,copied)
        if sha256(target)!=p['sourceFingerprint'] or sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Library changed during edit copy.')
        write_json(d/'vector-edit.json',{k:p[k] for k in ('scope','index','old','operation','replacement','vectorId','affectedScopes')})
        return run_owned_process(self.native_command(d,p),d,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def verify(self,d,p,native_completed):
        self.preflight(p);target=checked_path(str(d/'library.olb'),(d,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Edited library exceeds128MiB.')
        if native_completed:
            receipt=d/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'vectorId':p['vectorId']}:
                raise CadenceError('invalid_worker_result','Native vector edit receipt mismatch.')
        graph,_=self._read_graph(target,d)
        normalized=normalize_target_font(graph,p['scope'][-1],p['index'],p['operation'],p['replacement']['kind'] if p['replacement'] else None)
        if digest(normalized)!=p['expectedGraphDigest']:raise CadenceError('library_vector_mismatch','Edited library differs from the declared vector change or modeled preservation graph.','verify')
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Edited library changed during independent verification.')
        ident=d.name.removeprefix('plan-')
        artifact={'artifactId':'library-'+ident,'kind':'capture_edited_library','workspaceRelativePath':'library.olb',
          'sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],
          'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,
          'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'declaredVectorEditVerified':True,
          'modeledLibraryPreservationVerified':True,'affectedScopes':p['affectedScopes'],'sourceModified':False,'designCacheUpdated':False,
          'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),
          'notChecked':['rendered_appearance','unmodeled_library_properties','unreferenced_native_objects','target_default_font_inheritance','dsn_cache','instance_connectivity','native_drc','external_footprint']}
