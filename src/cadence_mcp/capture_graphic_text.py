"""Explicit page text addition via native definition coordinates, with modeled preservation."""
import copy,json
from datetime import datetime,timezone
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_wire import point,inventory,connection_digest
from .capture_page_vectors import query_page_vectors
from .capture_references import read_units
from .capture_cache_replace import read_state
from .capture_display_fonts import font_fields
from .core import CadenceError,checked_path,sha256,write_json
from .environment import ADAPTERS
from .isolated_jobs import digest

def declaration(text,location,width,height,rotation,mirror,font):
    if not isinstance(text,str) or not 1<=len(text)<=4096 or '\x00' in text or '\r' in text or any(0xD800<=ord(c)<=0xDFFF for c in text):raise CadenceError('invalid_graphic_text','Use 1..4096 literal characters and LF newlines; NUL/CR/surrogates are invalid.')
    if not point(location) or any(type(v) is not int for v in (width,height,rotation,mirror)) or not 1<=width<=100000 or not 1<=height<=100000 or rotation not in range(4) or mirror not in (0,1):raise CadenceError('invalid_graphic_text','Declare bounded page anchor, positive local box dimensions, rotation0..3 and mirror0..1.')
    fields=font_fields(font)
    if fields[12]!=1:raise CadenceError('unsupported_font_quality','Only quality1 has retained native persistence; other quality values remain unaccepted.')
    x,y=location
    for _ in range(rotation):x,y=-y,x
    if mirror:x=-x
    bounds=[x,y,x+width,y+height]
    if not point([x,y]) or not point(bounds[2:]):raise CadenceError('invalid_graphic_text','Transformed local text box exceeds coordinate bounds.')
    points=[[x,y],[x,y],[x+width,y],[x+width,y+height],[x,y+height]];world=[]
    for px,py in points:
        if mirror:px=-px
        for _ in range(rotation):px,py=py,-px
        if not point([px,py]):raise CadenceError('invalid_graphic_text','Page text box exceeds coordinate bounds.')
        world.append([px,py])
    return {'kind':'text','location':[0,0],'rotationCode':rotation,'mirrorCode':mirror,'localDescriptor':['text',text,[x,y],bounds,fields,0],'pageControlPoints':world}

def page_rows(capture,sid,page_id):
    result=[];cursor=None
    while True:
        q=query_page_vectors(capture,sid,page_id,cursor,1000)
        if not q['supportedGeometryComplete']:raise CadenceError('unsupported_graphics','Complete modeled graphic preservation requires supported vectors on every page.')
        result.extend({k:copy.deepcopy(v) for k,v in row.items() if k not in {'objectId','pageId','nativeId','index','nativeTypeCode'}} for row in q['items'])
        cursor=q['nextCursor']
        if cursor is None:return result

def graphic_state(capture,sid,target=None,added=None):
    data=capture._session(sid)['data'];out=[]
    if len(data['page'])>64:raise CadenceError('input_limit','Text preservation supports at most64 pages.')
    seen=set()
    for page in data['page']:
        sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId']);scope=(sch['name'],page['name'])
        if scope in seen:raise CadenceError('ambiguous_target','Page semantic identities must be unique.')
        seen.add(scope);rows=page_rows(capture,sid,page['objectId'])
        if page['objectId']==target:rows.append(copy.deepcopy(added))
        out.append({'scope':list(scope),'digest':digest(rows)})
    return sorted(out,key=lambda r:r['scope'])

class CaptureGraphicTexts(CapturePropertyEdits):
    kind='capture_graphic_text'
    def plan(self,sid,page_id,text,location,width,height,rotation=0,mirror=0,font=None):
        added=declaration(text,location,width,height,rotation,mirror,{} if font is None else font)
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('invalid_scope','Page is outside this immutable session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if any(len(v)>512 or '\x00' in v for v in (sch['name'],page['name'])):raise CadenceError('input_limit','Page locator exceeds bounds.')
            directory=session['design'].parent;units=read_units(self.capture,sid)
            p={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'schematicName':sch['name'],'pageName':page['name'],'pageAnchor':location,'localWidth':width,'localHeight':height,'added':added,'definitionDigest':definition_baseline(data),'connectionDigest':connection_digest(data,inventory(self.capture,sid)),'instanceDigest':digest(read_state(self.config,session['design'],directory,units)),'expectedGraphics':graphic_state(self.capture,sid,page_id,added)}
            if len(json.dumps(p,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Text baseline exceeds48KiB.')
            self.capture._session(sid);return self.create_plan(p)
    def preview(self,p):return {k:p[k] for k in ('schematicName','pageName','pageAnchor','localWidth','localHeight','added','sourceFingerprint')}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Text source changed after planning.')
    def native_command(self,directory,p):
        spec=directory/'text-spec.json';write_json(spec,{k:p[k] for k in ('schematicName','pageName','added')})
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'write_graphic_text.tcl',self.config.install_root,directory/'design.dsn',spec,directory/'native-result.json']
    def verify(self,directory,p,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Text output exceeds128MiB.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'add_graphic_text'}:raise CadenceError('invalid_worker_result','Text save receipt mismatch.')
        cap=CaptureService(self.config);cap.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}};sid=cap.open('output')['sessionId']
        try:
            data=cap.sessions[sid]['data'];units=read_units(cap,sid)
            if definition_baseline(data)!=p['definitionDigest'] or connection_digest(data,inventory(cap,sid))!=p['connectionDigest']:raise CadenceError('graphic_connectivity_changed','Text changed modeled definitions or connections.','verify')
            if digest(read_state(self.config,target,directory,units))!=p['instanceDigest']:raise CadenceError('graphic_instance_changed','Text changed modeled existing instances.','verify')
            if graphic_state(cap,sid)!=p['expectedGraphics']:raise CadenceError('graphic_text_mismatch','Text or ordered existing graphics differ from declared preservation.','verify')
        finally:cap.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Text output changed during verification.')
        ident=directory.name.removeprefix('plan-');artifact={'artifactId':'graphic-text-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'sourceModified':False,'independentReopenVerified':True,'nativeCompletionVerified':native_completed,'pageAnchorVerified':True,'modeledGraphicsAndInstancesPreserved':True,'definitionAndConnectionBaselinePreserved':True,'designPassed':None,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['rendered_glyph_bounds','page_clipping','titleblock_and_nested_symbols','instance_display_fonts','unmodeled_properties','occurrence_connectivity','native_drc']}
