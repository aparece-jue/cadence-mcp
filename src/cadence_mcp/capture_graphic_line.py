"""Owned decorative line addition; no electrical-wire operation."""
from collections import Counter
from datetime import datetime,timezone
import json
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_wire import point,inventory,connection_digest
from .core import CadenceError,checked_path,sha256,new_id
from .environment import ADAPTERS,run_tcl

def line_key(row):return json.dumps(row,sort_keys=True,separators=(',',':'))
def added_line(start,end):
    return {'localStart':[0,0],'localEnd':[end[0]-start[0],end[1]-start[1]],'location':start,
            'start':start,'end':end,'rotationCode':0,'mirrorCode':0}
def read_lines(config,design,directory,schematic,page):
    before=sha256(design);output=directory/(new_id('graphic-lines')+'.json')
    run_tcl(config,'graphic_line_probe.tcl',[str(design),str(output),schematic,page,'0','0','1','0','read'],directory)
    if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Graphic line inventory exceeds limit.')
    try:
        data=json.loads(output.read_text(encoding='utf-8'))
        if set(data)!={'lines'} or not isinstance(data['lines'],list) or len(data['lines'])>100000:raise ValueError()
        for row in data['lines']:
            if set(row)!={'localStart','localEnd','location','start','end','rotationCode','mirrorCode'}:raise ValueError()
            if not all(point(row[k]) for k in ('localStart','localEnd','location','start','end')):raise ValueError()
            if type(row['rotationCode']) is not int or type(row['mirrorCode']) is not int:raise ValueError()
    except (ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_worker_result','Malformed graphic line inventory.') from error
    if sha256(design)!=before:raise CadenceError('target_changed','Design changed while reading graphic lines.')
    return data['lines']

class CaptureGraphicLines(CapturePropertyEdits):
    kind='capture_graphic_line'
    def plan(self,sid,page_id,start,end):
        if not point(start) or not point(end) or start==end or not point([end[0]-start[0],end[1]-start[1]]):raise CadenceError('invalid_graphic_geometry','Provide two distinct bounded integer endpoints.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data']
            page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('object_not_found','Page is outside this session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            if any(len(n)>512 or '\x00' in n for n in (sch['name'],page['name'])):raise CadenceError('input_limit','Page locator exceeds literal bound.')
            directory=session['design'].parent
            old=read_lines(self.config,session['design'],directory,sch['name'],page['name'])
            expected=Counter(map(line_key,old));expected[line_key(added_line(start,end))]+=1
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'schematicName':sch['name'],'pageName':page['name'],
                     'start':start,'end':end,'expectedLines':dict(expected),'definitionDigest':definition_baseline(data),'connectionDigest':connection_digest(data,inventory(self.capture,sid))}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Graphic line baseline exceeds durable plan bound.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {**{k:p[k] for k in ('schematicName','pageName','start','end','sourceFingerprint')},'operation':'add_decorative_line','electricalObjectsWillBeModified':False}
    def preflight(self,p):
        source=checked_path(p['sourceDesign'],(self.config.workspace_root,))
        if sha256(source)!=p['sourceFingerprint']:raise CadenceError('target_changed','Graphic line source changed after planning.')
    def native_command(self,directory,p):
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'graphic_line_probe.tcl',self.config.install_root,directory/'design.dsn',directory/'native-result.json',p['schematicName'],p['pageName'],*map(str,p['start']),*map(str,p['end']),'add']
    def verify(self,directory,p,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Graphic output exceeds limit.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'add_graphic_line'}:raise CadenceError('invalid_worker_result','Graphic save receipt mismatch.')
        verifier=CaptureService(self.config);verifier.workspaces['output']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        sid=verifier.open('output')['sessionId']
        try:
            data=verifier.sessions[sid]['data']
            if definition_baseline(data)!=p['definitionDigest'] or connection_digest(data,inventory(verifier,sid))!=p['connectionDigest']:raise CadenceError('graphic_connectivity_changed','Decorative line changed definitions or connections.','verify')
            lines=read_lines(self.config,target,directory,p['schematicName'],p['pageName'])
            if dict(Counter(map(line_key,lines)))!=p['expectedLines']:raise CadenceError('graphic_line_mismatch','Saved graphic lines differ from explicit endpoint expectations.','verify')
        finally:verifier.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Graphic output changed during verification.')
        ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'graphic-line-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'sourceModified':False,'independentReopenVerified':True,'nativeCompletionVerified':native_completed,'definitionAndConnectionBaselinePreserved':True,'designPassed':None,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),'notChecked':['occurrence_connectivity','native_drc','rendered_bounds','line_style_width_color','text_fonts','other_graphic_types','titleblock_editing','other_part_properties']}
