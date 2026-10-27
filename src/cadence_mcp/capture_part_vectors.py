"""Actual placed-part definition vectors and native page control points."""
import copy,json
from .core import CadenceError,new_id
from .environment import run_tcl
from .capture_page_vectors import normalize_page_vectors

def normalize_part_vectors(data,part,page,schematic):
    try:
        if not isinstance(data,dict) or set(data)!={'vectors','boxes','partId','schematicName','pageName','reference','location','rotationCode','mirrorCode','pins'}:raise ValueError('shape')
        if (data['partId'],data['reference'],data['pageName'],data['schematicName'])!=(part['objectId'],part['reference'],page['name'],schematic['name']):raise ValueError('target')
        rows=normalize_page_vectors(data['vectors'],page['objectId'],require_native_id=False)
        for index,row in enumerate(rows):
            if any(row[key]!=data[key] for key in ('location','rotationCode','mirrorCode')):raise ValueError('pose')
            row.update(objectId=part['objectId']+'/vector-'+str(index+1),partId=part['objectId'])
        return rows
    except (ValueError,KeyError,TypeError) as error:raise CadenceError('invalid_worker_result','Invalid placed-part vector document.','decode') from error

def query_part_vectors(capture,sid,part_id,cursor=None,limit=100):
    with capture.lock:
        session=capture._session(sid)
        if type(limit) is not int or not 1<=limit<=1000:raise CadenceError('invalid_query','Use a page size from1 to1000.')
        part=next((p for p in session['data']['part'] if p['objectId']==part_id),None)
        if part is None:raise CadenceError('object_not_found','Part is outside this immutable definition session.')
        page=next(p for p in session['data']['page'] if p['objectId']==part['pageId'])
        sch=next(s for s in session['data']['schematic'] if s['objectId']==part['schematicId'])
        signature=(part_id,limit,session['revision']);cursors=session.setdefault('partVectorCursors',{});offset=0
        if cursor is not None:
            saved=cursors.get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Cursor belongs to one session, part, revision and page size.')
            offset=saved[1]
        cache=session.setdefault('partVectors',{})
        if part_id not in cache:
            directory=session['design'].parent;output=directory/(new_id('part-vectors')+'.json')
            run_tcl(capture.config,'inspect_part_vectors.tcl',[str(session['design']),str(output),part_id,'100000','10000'],directory)
            capture._session(sid)
            try:
                if not output.is_file() or output.stat().st_size>32*1024*1024:raise ValueError('output')
                cache[part_id]=normalize_part_vectors(json.loads(output.read_text(encoding='utf-8')),part,page,sch)
            except (OSError,ValueError) as error:raise CadenceError('invalid_worker_result','Missing or invalid bounded part-vector output.','decode') from error
            output.unlink()
        rows=cache[part_id];next_cursor=None
        if offset+limit<len(rows):
            if len(cursors)>=10000:raise CadenceError('cursor_limit','Open a new session.')
            next_cursor=new_id('part-vector-cursor');cursors[next_cursor]=(signature,offset+limit)
        unsupported=sum(row['kind']=='unsupported' for row in rows)
        return {'sessionId':sid,'revision':session['revision'],'partId':part_id,'pageId':page['objectId'],'items':copy.deepcopy(rows[offset:offset+limit]),'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,'unsupportedCount':unsupported,'supportedGeometryComplete':unsupported==0,'order':'native_defining_part_vector_order','identity':'revision_scoped_part_and_vector_index','descriptorCoordinateSpace':'defining_part_local','controlPointCoordinateSpace':'page_native_integer','renderedBoundsVerified':False,'electricalConnectivityVerified':False,'notChecked':['rendered_glyph_and_stroke_bounds','display_property_geometry','pin_graphics','nested_symbol_and_OLE_geometry','occurrence_geometry','electrical_connectivity','native_drc']}
