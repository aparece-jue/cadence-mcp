"""Explicit existing display-font edits with native identity and complete modeled state checks."""
import copy,json
from datetime import datetime,timezone
from pydantic import ValidationError
from .core import CadenceError,checked_path,new_id,sha256,write_json
from .environment import ADAPTERS,run_tcl
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .capture_references import read_units
from .capture_cache_replace import read_state,unit_graph
from .capture_wire import inventory,connection_digest
from .library_vectors import VectorFont

FONT_KEYS=tuple(VectorFont.model_fields)

def font_fields(value):
    try:font=VectorFont.model_validate(value).model_dump()
    except (ValidationError,TypeError,ValueError) as error:raise CadenceError('invalid_display_font','Declare a complete bounded font descriptor; zero height/control characters are invalid.') from error
    return [int(font[k]) if type(font[k]) is bool else font[k] for k in FONT_KEYS]

def normalize_fonts(rows,units):
    try:
        if not isinstance(rows,list) or len(rows)!=len(units) or len(rows)>128:raise ValueError('coverage')
        ids={u['nativeId'] for u in units.values()};seen=set();result=[];name_bytes=0
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'nativeId','fonts'} or type(row['nativeId']) is not int or row['nativeId'] not in ids or row['nativeId'] in seen:raise ValueError('instance')
            seen.add(row['nativeId']);fonts=row['fonts'];names=set()
            if not isinstance(fonts,list) or len(fonts)>512:raise ValueError('count')
            for prop in fonts:
                if not isinstance(prop,dict) or set(prop)!={'name','font','fontDefault','defaultFontType'} or not isinstance(prop['name'],str) or not 1<=len(prop['name'])<=256 or prop['name'] in names or '\x00' in prop['name']:raise ValueError('name')
                if type(prop['fontDefault']) is not int or prop['fontDefault'] not in (0,1) or type(prop['defaultFontType']) is not int:raise ValueError('font inheritance')
                names.add(prop['name']);name_bytes+=len(prop['name'].encode('utf-8'));font=prop['font']
                if not isinstance(font,list) or len(font)!=14 or not isinstance(font[0],str) or len(font[0])>64 or any(c in font[0] for c in '\x00\r\n') or any(type(v) is not int or not -2147483648<=v<=2147483647 for v in font[1:]):raise ValueError('descriptor')
                if any(font[i] not in (0,1) for i in (6,7,8)):raise ValueError('boolean')
            result.append({'nativeId':row['nativeId'],'fonts':sorted(copy.deepcopy(fonts),key=lambda p:p['name'])})
        if seen!=ids or name_bytes>1024*1024:raise ValueError('identity/budget')
        return sorted(result,key=lambda r:r['nativeId'])
    except (ValueError,KeyError,TypeError,AttributeError) as error:raise CadenceError('invalid_display_fonts','Native font descriptors must cover every instance exactly once.','decode') from error

def read_fonts(config,design,directory,units):
    output=directory/(new_id('display-fonts')+'.json');run_tcl(config,'inspect_display_fonts.tcl',[str(design),str(output)],directory)
    if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Font document exceeds32MiB.')
    rows=normalize_fonts(json.loads(output.read_text(encoding='utf-8')),units);output.unlink();return rows

def target_font(rows,unit,name):
    if not isinstance(name,str) or not 1<=len(name)<=128 or '\x00' in name:raise CadenceError('invalid_property_name','Choose an exact existing display property.')
    found=[p for row in rows if row['nativeId']==unit['nativeId'] for p in row['fonts'] if p['name']==name]
    if len(found)!=1:raise CadenceError('display_property_not_found','Display property is absent or ambiguous.')
    return found[0]['font']

def query_font(capture,sid,part_id,name):
    with capture.lock:
        s=capture._session(sid);units=read_units(capture,sid);unit=units.get(part_id)
        if unit is None:raise CadenceError('object_not_found','Part is outside this definition session.')
        rows=read_fonts(capture.config,s['design'],s['design'].parent,units);value=target_font(rows,unit,name);prop=next(p for r in rows if r['nativeId']==unit['nativeId'] for p in r['fonts'] if p['name']==name);capture._session(sid)
        return {'partId':part_id,'nativeId':unit['nativeId'],'property':name,'font':{k:bool(value[i]) if i in (6,7,8) else value[i] for i,k in enumerate(FONT_KEYS)},'fontDefault':bool(prop['fontDefault']),'defaultFontType':prop['defaultFontType'],'revision':s['revision'],'scope':'instance_definition_display','readOnly':True,'notChecked':['font_availability','rendered_bounds','occurrence_font_override']}

class CaptureDisplayFonts(CapturePropertyEdits):
    kind='capture_display_font'
    def plan(self,sid,part_id,name,font):
        new=font_fields(font)
        with self.capture.lock:
            cap=self.capture;s=cap._session(sid);units=read_units(cap,sid);unit=units.get(part_id)
            if unit is None:raise CadenceError('object_not_found','Part is outside this definition session.')
            data=s['data'];parts={p['objectId']:p for p in data['part']};part=parts[part_id]
            if sum(row['name']==unit['schematicName'] for row in data['schematic'])!=1 or sum(p['schematicId']==part['schematicId'] and p['name']==unit['pageName'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Target schematic and page must have unique semantic names.')
            fonts=read_fonts(self.config,s['design'],s['design'].parent,units);old=target_font(fonts,unit,name)
            old_prop=next(p for row in fonts if row['nativeId']==unit['nativeId'] for p in row['fonts'] if p['name']==name)
            if old==new and old_prop['fontDefault']==0:raise CadenceError('no_change','Requested explicit font already matches.')
            expected=copy.deepcopy(fonts)
            for row in expected:
                if row['nativeId']==unit['nativeId']:
                    for p in row['fonts']:
                        if p['name']==name:p.update(font=new,fontDefault=0)
            evidence={'state':read_state(self.config,s['design'],s['design'].parent,units),'units':unit_graph(units),'fonts':expected}
            path=s['design'].parent/(new_id('expected-display-font')+'.json');write_json(path,evidence)
            payload={k:unit[k] for k in ('nativeId','schematicName','pageName','reference')}
            payload.update(sourceDesign=str(s['design']),sourceFingerprint=s['revision'],partId=part_id,property=name,oldFont=old,newFont=new,oldFontDefault=old_prop['fontDefault'],oldDefaultFontType=old_prop['defaultFontType'],expectedEvidence=str(path),expectedEvidenceHash=sha256(path),definitionDigest=definition_baseline(data),connectionDigest=connection_digest(data,inventory(cap,sid)))
            cap._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('partId','nativeId','schematicName','pageName','reference','property','oldFont','newFont','sourceFingerprint')}
    def preflight(self,p):
        for path,key in (('sourceDesign','sourceFingerprint'),('expectedEvidence','expectedEvidenceHash')):
            if sha256(checked_path(p[path],(self.config.workspace_root,)))!=p[key]:raise CadenceError('target_changed','Frozen display-font source or expected state changed.')
    def execute(self,d,p,cancel,on_started):
        write_json(d/'font-request.json',{k:p[k] for k in ('nativeId','schematicName','pageName','reference','property','oldFont','newFont','oldFontDefault','oldDefaultFontType')})
        return super().execute(d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_display_font.tcl',self.config.install_root,d/'design.dsn',d/'font-request.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        self.preflight(p);target=checked_path(str(d/'design.dsn'),(d,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Font output exceeds128MiB.')
        if native_completed:
            f=d/'native-result.json'
            if f.stat().st_size>4096 or json.loads(f.read_text(encoding='utf-8'))!={'saved':True,'phase':'save','message':''}:raise CadenceError('invalid_worker_result','Display-font receipt differs.')
        evidence=json.loads(checked_path(p['expectedEvidence'],(self.config.workspace_root,)).read_text(encoding='utf-8'))
        cap=CaptureService(self.config);cap.workspaces['font']={'directory':d,'manifest':{'copiedFingerprint':before}};sid=cap.open('font')['sessionId']
        try:
            data=cap.sessions[sid]['data'];units=read_units(cap,sid)
            if definition_baseline(data)!=p['definitionDigest'] or connection_digest(data,inventory(cap,sid))!=p['connectionDigest']:raise CadenceError('display_font_connectivity_changed','Font edit changed original definitions or connection objects.','verify')
            if unit_graph(units)!=evidence['units'] or read_state(self.config,target,d,units)!=evidence['state']:raise CadenceError('display_font_instance_state_changed','Font edit changed geometry, ownership or modeled property/display state.','verify')
            if read_fonts(self.config,target,d,units)!=evidence['fonts']:raise CadenceError('display_font_persistence_mismatch','Saved target font or an unrelated instance font differs from the frozen complete descriptor table.','verify')
        finally:cap.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Font output changed during verification.')
        ident=d.name.removeprefix('plan-');artifact={'artifactId':'display-font-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['sourceFingerprint'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'sourceModified':False,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'allDisplayFontsVerified':True,'modeledAllInstanceStateVerified':True,'observedFont':p['newFont'],'outputWorkspaceRelativePath':d.relative_to(self.config.workspace_root).as_posix(),'notChecked':['font_availability','rendered_text_bounds','occurrence_font_override','cache_vector_graphics','native_drc']}
