"""Typed page comment-vector definitions and native transformed control points."""
import copy,json
from .core import CadenceError,new_id
from .environment import run_tcl
from .library_vector_query import validate_descriptor

def control_point_count(v):
    if v[0]=='line':return 2
    if v[0] in ('box','ellipse'):return 4
    if v[0]=='arc':return 6
    if v[0] in ('polygon','polyline','bezier'):return len(v[1])
    if v[0] in ('text','bitmap'):return 5
    raise ValueError('Unsupported page vector')

def normalize_page_vectors(rows,page_id,*,require_native_id=True):
    try:
        if not isinstance(rows,list) or len(rows)>4096:raise ValueError('count')
        points=0;text=0;result=[]
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or set(row)!={'index','nativeId','nativeTypeCode','kind','location','rotationCode','mirrorCode','localDescriptor','pageControlPoints'}:raise ValueError('shape')
            if type(row['index']) is not int or row['index']!=index or any(type(row[k]) is not int for k in ('nativeTypeCode','rotationCode','mirrorCode')) or (type(row['nativeId']) is not int if require_native_id else row['nativeId'] is not None) or row['rotationCode'] not in range(4) or row['mirrorCode'] not in (0,1):raise ValueError('identity/pose')
            def point(p):return isinstance(p,list) and len(p)==2 and all(type(v) is int and -2147483648<=v<=2147483647 for v in p)
            if not point(row['location']) or not isinstance(row['pageControlPoints'],list) or any(not point(p) for p in row['pageControlPoints']):raise ValueError('points')
            v=row['localDescriptor']
            if row['kind']=='unsupported':
                if v is not None or row['pageControlPoints']:raise ValueError('unsupported geometry')
            else:
                validate_descriptor(v)
                if row['kind']!=v[0] or len(row['pageControlPoints'])!=control_point_count(v):raise ValueError('descriptor/control coverage')
                points+=len(row['pageControlPoints']);text+=len(v[1]) if v[0]=='text' else 0
            result.append({'objectId':page_id+'/graphic-'+str(index+1),'pageId':page_id,**copy.deepcopy(row)})
        if points>65536 or text>262144:raise ValueError('budget')
        return result
    except (ValueError,KeyError,TypeError,AttributeError,IndexError) as error:raise CadenceError('invalid_worker_result','Invalid bounded page-vector descriptors.','decode') from error

def query_page_vectors(capture,sid,page_id,cursor=None,limit=100):
    with capture.lock:
        session=capture._session(sid)
        if type(limit) is not int or not 1<=limit<=1000:raise CadenceError('invalid_query','Use a page size from1 to1000.')
        page=next((p for p in session['data']['page'] if p['objectId']==page_id),None)
        if page is None:raise CadenceError('invalid_scope','Page is outside this immutable design session.')
        sch=next(s for s in session['data']['schematic'] if s['objectId']==page['schematicId'])
        if sum(s['name']==sch['name'] for s in session['data']['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in session['data']['page'])!=1:raise CadenceError('ambiguous_target','Page semantic locator must be unique.')
        signature=(page_id,limit,session['revision']);cursors=session.setdefault('pageVectorCursors',{});offset=0
        if cursor is not None:
            saved=cursors.get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Page-vector cursor is bound to session, page, revision and limit.')
            offset=saved[1]
        cache=session.setdefault('pageVectors',{})
        if page_id not in cache:
            directory=session['design'].parent;output=directory/(new_id('page-vectors')+'.json');run_tcl(capture.config,'inspect_page_vectors.tcl',[str(session['design']),str(output),sch['name'],page['name']],directory);capture._session(sid)
            if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Page vectors exceed32MiB.')
            cache[page_id]=normalize_page_vectors(json.loads(output.read_text(encoding='utf-8')),page_id);output.unlink()
        rows=cache[page_id];next_cursor=None
        if offset+limit<len(rows):
            if len(cursors)>=10000:raise CadenceError('cursor_limit','Open a new session.')
            next_cursor=new_id('page-vector-cursor');cursors[next_cursor]=(signature,offset+limit)
        unsupported=sum(r['kind']=='unsupported' for r in rows)
        return {'sessionId':sid,'revision':session['revision'],'pageId':page_id,'items':copy.deepcopy(rows[offset:offset+limit]),'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,'unsupportedCount':unsupported,'supportedGeometryComplete':unsupported==0,'order':'native_comment_graphics_order','descriptorCoordinateSpace':'defining_graphic_local','controlPointCoordinateSpace':'page_native_integer','renderedBoundsVerified':False,'electricalConnectivityVerified':False,'notChecked':['rendered_glyph_bounds','symbol_instance_and_titleblock_vectors','nested_symbol_and_OLE_geometry','occurrence_geometry','electrical_connectivity','native_drc']}
