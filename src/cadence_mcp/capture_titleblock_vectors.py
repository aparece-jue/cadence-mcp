"""Immutable titleblock definition vectors, separate from occurrence/display rendering."""
import copy,json
from .core import CadenceError,new_id
from .environment import run_tcl
from .capture_objects import query_objects
from .capture_geometry import point
from .capture_page_vectors import normalize_page_vectors

def normalize_titleblock_vectors(data,target):
    try:
        attrs=target['attributes']
        if not isinstance(data,dict) or set(data)!={'nativeId','name','sourceSymbol','location','rotationCode','mirrorCode','vectors'}:raise ValueError('shape')
        if type(data['nativeId']) is not int or data['nativeId']!=target['nativeId']:raise ValueError('target')
        if not point(data['location']) or any(type(data[k]) is not int for k in ('rotationCode','mirrorCode')):raise ValueError('pose types')
        if any(data[k]!=attrs[k] for k in ('name','location','rotationCode','mirrorCode')):raise ValueError('target pose')
        if not isinstance(data['sourceSymbol'],str) or not 1<=len(data['sourceSymbol'])<=4096:raise ValueError('symbol')
        rows=normalize_page_vectors(data['vectors'],target['pageId'],require_native_id=False)
        for i,row in enumerate(rows):
            if any(row[k]!=attrs[k] for k in ('location','rotationCode','mirrorCode')):raise ValueError('row pose')
            row.update(objectId=target['objectId']+'/vector-'+str(i+1),titleblockId=target['objectId'])
        return rows
    except (ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_worker_result','Invalid titleblock vector document.','decode') from error

def query_titleblock_vectors(capture,sid,target_id,cursor=None,limit=100):
    with capture.lock:
        session=capture._session(sid)
        if type(limit) is not int or not 1<=limit<=1000:raise CadenceError('invalid_query','Use a page size from1 to1000.')
        query_objects(capture,sid,'graphics','titleblock',None,None,1)
        target=next((x for x in session['objectInventories']['graphics'] if x['kind']=='titleblock' and x['objectId']==target_id),None)
        if target is None:raise CadenceError('object_not_found','Titleblock is outside this immutable session.')
        page=next(p for p in session['data']['page'] if p['objectId']==target['pageId'])
        sch=next(s for s in session['data']['schematic'] if s['objectId']==page['schematicId'])
        if sum(s['name']==sch['name'] for s in session['data']['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in session['data']['page'])!=1:raise CadenceError('ambiguous_target','Page locator must be unique.')
        signature=(target_id,limit,session['revision']);cursors=session.setdefault('titleblockVectorCursors',{});offset=0
        if cursor is not None:
            saved=cursors.get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Cursor belongs to one session, titleblock, revision and page size.')
            offset=saved[1]
        cache=session.setdefault('titleblockVectors',{})
        if target_id not in cache:
            directory=session['design'].parent;output=directory/(new_id('titleblock-vectors')+'.json')
            run_tcl(capture.config,'inspect_titleblock_vectors.tcl',[str(session['design']),str(output),sch['name'],page['name'],str(target['nativeId'])],directory)
            capture._session(sid)
            try:
                if not output.is_file() or output.stat().st_size>32*1024*1024:raise ValueError('output')
                data=json.loads(output.read_text(encoding='utf-8'));rows=normalize_titleblock_vectors(data,target)
            except (OSError,ValueError) as error:raise CadenceError('invalid_worker_result','Invalid bounded titleblock vector output.','decode') from error
            output.unlink();cache[target_id]=(rows,data['sourceSymbol'])
        rows,symbol=cache[target_id];next_cursor=None
        if offset+limit<len(rows):
            if len(cursors)>=10000:raise CadenceError('cursor_limit','Open a new session.')
            next_cursor=new_id('titleblock-vector-cursor');cursors[next_cursor]=(signature,offset+limit)
        unsupported=sum(row['kind']=='unsupported' for row in rows)
        return {'sessionId':sid,'revision':session['revision'],'titleblockId':target_id,'pageId':page['objectId'],'sourceSymbol':symbol,'items':copy.deepcopy(rows[offset:offset+limit]),'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,'unsupportedCount':unsupported,'supportedGeometryComplete':unsupported==0,'order':'native_titleblock_definition_vector_order','identity':'revision_scoped_titleblock_and_vector_index','descriptorCoordinateSpace':'defining_titleblock_symbol_local','controlPointCoordinateSpace':'page_native_integer','renderedBoundsVerified':False,'electricalConnectivityVerified':False,'notChecked':['rendered_glyph_and_stroke_bounds','display_property_geometry','effective_occurrence_text','nested_symbol_and_OLE_geometry','occurrence_geometry','electrical_connectivity','native_drc']}
