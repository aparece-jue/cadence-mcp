"""Read basic native library graphics from a bound immutable library copy."""
import json
import re
from .core import CadenceError,new_id
from .environment import run_tcl

def validate_descriptor(v):
    def ints(values,n):
        return isinstance(values,list) and len(values)==n and all(type(x) is int and -2147483648<=x<=2147483647 for x in values)
    if not isinstance(v,list) or not v or not isinstance(v[0],str):raise ValueError('Invalid vector')
    kind=v[0]
    lengths={'line':5,'box':6,'ellipse':6,'arc':6,'polygon':6,'polyline':4,'bezier':4,'fill':4,'text':6,'bitmap':6}
    if kind not in lengths or len(v)!=lengths[kind]:raise ValueError('Unsupported vector shape')
    if kind=='line':
        valid=ints(v[1],2) and ints(v[2],2);scalars=v[3:]
    elif kind in ('box','ellipse'):
        valid=ints(v[1],4);scalars=v[2:]
    elif kind=='arc':
        valid=ints(v[1],4) and ints(v[2],2) and ints(v[3],2);scalars=v[4:]
    elif kind in ('polygon','polyline','bezier'):
        valid=isinstance(v[1],list) and len(v[1])<=4096 and all(ints(p,2) for p in v[1]);scalars=v[2:]
    elif kind=='bitmap':
        valid=(ints(v[1],4) and ints(v[2],2) and ints(v[3],2)
               and all(x>0 for x in v[3]) and type(v[4]) is int and 0<v[4]<=16777216
               and isinstance(v[5],str) and re.fullmatch(r'[0-9a-f]{64}',v[5]) is not None)
        scalars=[]
    elif kind=='fill':
        valid=ints(v[1],2);scalars=v[2:]
    else:
        valid=(isinstance(v[1],str) and len(v[1])<=65536 and ints(v[2],2) and ints(v[3],4)
               and isinstance(v[4],list) and len(v[4])==14 and isinstance(v[4][0],str)
               and len(v[4][0])<=255 and ints(v[4][1:],13)
               and type(v[5]) is int and v[5] in (0,1))
        scalars=[]
    if not valid or any(type(x) is not int for x in scalars):raise ValueError('Invalid vector fields')
    return v

def query_library_vectors(library,library_id,part_id,cursor=None,limit=100):
    with library.lock:
        session=library._session(library_id)
        if type(limit) is not int or not 1<=limit<=1000 or not isinstance(part_id,str):
            raise CadenceError('invalid_query','Specify one bound library part and a page size from1 to1000.')
        parts=[p for p in session['data']['part'] if p['objectId']==part_id]
        if len(parts)!=1:raise CadenceError('object_not_found','Library part does not belong to this session snapshot.')
        part=parts[0]
        package=next(p for p in session['data']['package'] if p['objectId']==part['packageId'])
        device=next(d for d in session['data']['device'] if d['objectId']==part['deviceId'])
        signature=json.dumps(['library_vectors',part_id,limit,session['revision']],ensure_ascii=False)
        offset=0
        if cursor is not None:
            saved=session['cursors'].get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Vector cursor does not belong to this query.')
            offset=saved[1]
        cache=session.setdefault('basicVectors',{})
        if part_id not in cache:
            directory=session['directory'];output=directory/(new_id('vectors')+'.json')
            run_tcl(library.config,'inspect_library_vectors.tcl',
                    [str(directory/'library.olb'),str(output),package['name'],device['designator'],part['name']],directory)
            library._session(library_id)
            try:
                if output.stat().st_size>32*1024*1024:raise ValueError('Output too large')
                rows=json.loads(output.read_text(encoding='utf-8'))
                if not isinstance(rows,list) or len(rows)!=1:raise ValueError('Ambiguous vector scope')
                row=rows[0]
                if (set(row)!={'package','designator','partName','vectors','signature'}
                    or (row['package'],row['designator'],row['partName'])!=(package['name'],device['designator'],part['name'])
                    or not isinstance(row['vectors'],list) or len(row['vectors'])>4096):raise ValueError('Mismatched vector scope')
                vectors=[validate_descriptor(v) for v in row['vectors']]
                if sum(len(v[1]) for v in vectors if v[0] in ('polygon','polyline','bezier'))>65536:raise ValueError('Point budget')
                if sum(len(v[1]) for v in vectors if v[0]=='text')>262144:raise ValueError('Text budget')
            except (ValueError,TypeError,KeyError,OSError) as error:
                raise CadenceError('invalid_worker_result','Invalid bounded library vector snapshot.','decode') from error
            cache[part_id]=[{'objectId':part_id+'/vector-'+str(i+1),'partId':part_id,'index':i,'kind':v[0],'descriptor':v}
                            for i,v in enumerate(vectors)]
        rows=cache[part_id];next_cursor=None
        if offset+limit<len(rows):
            if len(session['cursors'])>=10000:raise CadenceError('cursor_limit','Open a fresh library session.')
            next_cursor=new_id('vectorcursor');session['cursors'][next_cursor]=(signature,offset+limit)
        return {'libraryId':library_id,'partId':part_id,'revision':session['revision'],
                'items':rows[offset:offset+limit],'total':len(rows),'nextCursor':next_cursor,
                'complete':next_cursor is None,'scope':'library_basic_vectors','order':'native_draw_order',
                'renderedAppearanceVerified':False}
