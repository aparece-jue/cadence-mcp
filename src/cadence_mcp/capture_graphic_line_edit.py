"""Existing decorative-line edits with ordered graphics and native identity preservation."""
import copy
import json
import re
from datetime import datetime, timezone
from typing import Annotated
from pydantic import Field

from .capture import CaptureService
from .capture_graphic_line import CaptureGraphicLines, read_lines
from .capture_graphic_text import graphic_state, page_rows
from .capture_edit import definition_baseline
from .capture_cache_replace import read_state
from .capture_references import read_units
from .capture_wire import point, inventory, connection_digest
from .core import CadenceError, checked_path, sha256, write_json
from .environment import ADAPTERS
from .isolated_jobs import digest
from .library_vectors import VectorModel, Point


class GraphicLineChange(VectorModel):
    localStart: Point
    localEnd: Point
    location: Point
    rotation: Annotated[int, Field(ge=0, le=3)]
    mirror: Annotated[int, Field(ge=0, le=1)]
    lineStyle: Annotated[int, Field(ge=0, le=5)]
    lineWidth: Annotated[int, Field(ge=0, le=3)]
    lineColor: Annotated[int, Field(ge=1, le=48)]


def declaration(change):
    try:
        value=GraphicLineChange.model_validate(change).model_dump(mode='json')
    except (ValueError, TypeError) as error:
        raise CadenceError('invalid_graphic_line_edit','Declare complete bounded line geometry, pose, stroke and native color.') from error
    if value['localStart']==value['localEnd']:
        raise CadenceError('invalid_graphic_geometry','A decorative line must have distinct endpoints.')
    points=[]
    for x,y in (value['localStart'],value['localEnd']):
        if value['mirror']:x=-x
        x,y=[(x,y),(y,-x),(-x,-y),(-y,x)][value['rotation']]
        world=[x+value['location'][0],y+value['location'][1]]
        if not point(world):raise CadenceError('invalid_graphic_geometry','Transformed endpoints exceed coordinate bounds.')
        points.append(world)
    return value,dict(kind='line',location=value['location'],rotationCode=value['rotation'],mirrorCode=value['mirror'],
        localDescriptor=['line',value['localStart'],value['localEnd'],value['lineStyle'],value['lineWidth']],pageControlPoints=points)


def line_records_state(capture,sid,target_page=None,target_id=None,replacement=None):
    session=capture._session(sid);data=session['data'];result=[];seen=set();total=0
    if len(data['page'])>64:raise CadenceError('input_limit','Line edits support at most64 modeled pages.')
    for page in data['page']:
        sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId']);scope=(sch['name'],page['name'])
        if scope in seen:raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
        seen.add(scope)
        rows=copy.deepcopy(read_lines(capture.config,session['design'],session['design'].parent,*scope,True,True,True))
        total+=len(rows)
        if total>4096:raise CadenceError('input_limit','Line edit preservation exceeds4096 line records.')
        if len({r['nativeId'] for r in rows})!=len(rows):raise CadenceError('ambiguous_target','Native line IDs are not unique on the page.')
        if page['objectId']==target_page:
            matches=[i for i,r in enumerate(rows) if r['nativeId']==target_id]
            if len(matches)!=1:raise CadenceError('invalid_graphic_line_edit','Selected native line was not uniquely read.')
            if replacement is None:del rows[matches[0]]
            else:rows[matches[0]]=copy.deepcopy(replacement)
        result.append(dict(scope=list(scope),digest=digest(rows)))
    return sorted(result,key=lambda r:r['scope'])


class CaptureGraphicLineEdits(CaptureGraphicLines):
    def plan_edit(self,sid,graphic_id,operation,change=None):
        if operation not in ('update','delete') or (operation=='update')!=(change is not None):
            raise CadenceError('invalid_graphic_line_edit','Use update with a full change or delete without one.')
        value,added=declaration(change) if change is not None else (None,None)
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data']
            match=re.fullmatch(r'(.+)/graphic-([1-9][0-9]{0,3})',graphic_id) if isinstance(graphic_id,str) and len(graphic_id)<=256 else None
            if not match:raise CadenceError('invalid_graphic_line_edit','Use a graphicId from this session page-vector query.')
            if int(match[2])>4096:raise CadenceError('invalid_graphic_line_edit','Graphic index exceeds the bounded page query.')
            page=next((p for p in data['page'] if p['objectId']==match[1]),None)
            if page is None:raise CadenceError('invalid_scope','Graphic ID is outside this immutable session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:
                raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
            if any(len(n)>512 or '\x00' in n for n in (sch['name'],page['name'])):raise CadenceError('input_limit','Page locator exceeds bound.')
            page_rows(self.capture,sid,page['objectId']);rows=session['pageVectors'][page['objectId']];index=int(match[2])-1
            if index>=len(rows) or rows[index]['objectId']!=graphic_id or rows[index]['kind']!='line':
                raise CadenceError('invalid_graphic_line_edit','Select exactly one decorative line, not a wire or other graphic.')
            selected=rows[index]
            directory=session['design'].parent
            old_records=read_lines(self.config,session['design'],directory,sch['name'],page['name'],True,True,True)
            matches=[r for r in old_records if r['nativeId']==selected['nativeId']]
            if len(matches)!=1:raise CadenceError('invalid_graphic_line_edit','Native target line was not uniquely read.')
            old=matches[0]
            replacement=None
            if added is not None:
                replacement=dict(nativeId=selected['nativeId'],localStart=value['localStart'],localEnd=value['localEnd'],
                    location=value['location'],rotationCode=value['rotation'],mirrorCode=value['mirror'],
                    start=added['pageControlPoints'][0],end=added['pageControlPoints'][1],lineStyle=value['lineStyle'],
                    lineWidth=value['lineWidth'],lineColor=value['lineColor'],definitionColor=value['lineColor'])
            units=read_units(self.capture,sid)
            payload=dict(sourceDesign=str(session['design']),sourceFingerprint=session['revision'],operation=operation,
                schematicName=sch['name'],pageName=page['name'],targetIndex=index,targetNativeId=selected['nativeId'],
                oldLine=old,change=value,oldGraphic={k:copy.deepcopy(v) for k,v in selected.items() if k not in {'objectId','pageId','nativeId','index','nativeTypeCode'}},
                expectedGraphics=graphic_state(self.capture,sid,page['objectId'],added,index),
                expectedLineRecords=line_records_state(self.capture,sid,page['objectId'],selected['nativeId'],replacement),
                definitionDigest=definition_baseline(data),connectionDigest=connection_digest(data,inventory(self.capture,sid)),
                instanceDigest=digest(read_state(self.config,session['design'],directory,units)))
            if len(json.dumps(payload,ensure_ascii=False).encode('utf8'))>48000:raise CadenceError('plan_limit','Line edit baseline exceeds48KiB.')
            self.capture._session(sid)
            return self.create_plan(payload)

    def preview(self,p):
        if p.get('operation') not in ('update','delete'):return super().preview(p)
        return {k:p[k] for k in ('operation','schematicName','pageName','targetNativeId','oldLine','change','sourceFingerprint')}

    def native_command(self,directory,p):
        if p.get('operation') not in ('update','delete'):return super().native_command(directory,p)
        spec=directory/'line-spec.json';write_json(spec,dict(schema=1,**{k:p[k] for k in ('operation','schematicName','pageName','targetIndex','targetNativeId','oldLine','change')}))
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'write_graphic_line.tcl',self.config.install_root,directory/'design.dsn',spec,directory/'native-result.json']

    def verify(self,directory,p,native_completed):
        if p.get('operation') not in ('update','delete'):return super().verify(directory,p,native_completed)
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','Graphic output exceeds128MiB.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf8'))!={'saved':True,'operation':p['operation']+'_graphic_line'}:
                raise CadenceError('invalid_worker_result','Line edit save receipt differs.')
        cap=CaptureService(self.config);cap.workspaces['output']=dict(directory=directory,manifest=dict(copiedFingerprint=before));sid=cap.open('output')['sessionId']
        try:
            data=cap.sessions[sid]['data'];units=read_units(cap,sid)
            if definition_baseline(data)!=p['definitionDigest'] or connection_digest(data,inventory(cap,sid))!=p['connectionDigest']:
                raise CadenceError('graphic_connectivity_changed','Line edit changed modeled definitions or connections.','verify')
            if digest(read_state(self.config,target,directory,units))!=p['instanceDigest']:
                raise CadenceError('graphic_instance_changed','Line edit changed modeled instances.','verify')
            if graphic_state(cap,sid)!=p['expectedGraphics'] or line_records_state(cap,sid)!=p['expectedLineRecords']:
                raise CadenceError('graphic_line_mismatch','Ordered graphics, line identity/color or declared endpoints differ.','verify')
        finally:cap.close(sid)
        self.preflight(p)
        if sha256(target)!=before:raise CadenceError('target_changed','Line edit output changed during verification.')
        ident=directory.name.removeprefix('plan-')
        artifact=dict(artifactId='graphic-line-'+ident,kind='capture_edited_design',workspaceRelativePath='design.dsn',sha256=before,
            size=target.stat().st_size,producedByJob=ident,sourceFingerprint=p['sourceFingerprint'],createdAt=datetime.now(timezone.utc).isoformat(),validationState='validated')
        return dict(planId=ident,state='verified' if native_completed else 'verified_recovered',artifact=artifact,sourceModified=False,
            independentReopenVerified=True,nativeCompletionVerified=native_completed,definitionAndConnectionBaselinePreserved=True,
            nativeColorVerified=p['operation']=='update',graphicRemovalVerified=p['operation']=='delete',modeledGraphicsAndInstancesPreserved=True,
            lineIdentitiesAndColorsPreserved=True,designPassed=None,outputWorkspaceRelativePath=directory.relative_to(self.config.workspace_root).as_posix(),
            notChecked=['rendered_bounds','page_clipping','titleblock_and_nested_symbols','instance_display_fonts','unmodeled_properties','occurrence_connectivity','native_drc'])
