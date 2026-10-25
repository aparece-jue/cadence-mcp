"""Read native global/port/offpage definitions from immutable OLB sessions."""
import json
from .core import CadenceError,new_id
from .environment import run_tcl
KINDS={33:'global',34:'port',35:'offpage'}

def symbol_rows(raw):
    if not isinstance(raw,list) or len(raw)>10000:raise CadenceError('invalid_worker_result','Invalid bounded native symbol list.')
    result=[];seen=set()
    for row in raw:
        if not isinstance(row,dict) or set(row)!={'name','objectType'} or type(row['name']) is not str or type(row['objectType']) is not int or not 1<=len(row['name'])<=512 or any(ord(c)<32 or ord(c)==127 for c in row['name']):raise CadenceError('invalid_worker_result','Invalid native symbol record.')
        if row['objectType'] not in KINDS:continue
        kind=KINDS[row['objectType']];identity=(kind,row['name'].casefold())
        if identity in seen:raise CadenceError('ambiguous_net_symbol','Duplicate kind/name symbol definition.')
        seen.add(identity);result.append({'kind':kind,'name':row['name'],'nativeTypeCode':row['objectType']})
    result.sort(key=lambda row:(row['kind'],row['name']))
    return [{'symbolId':'net-symbol-'+str(i+1),**row} for i,row in enumerate(result)]

def query_net_symbols(library,lid,kind=None,cursor=None,limit=100):
    with library.lock:
        session=library._session(lid)
        if kind not in (None,'global','port','offpage') or type(limit) is not int or not 1<=limit<=1000:raise CadenceError('invalid_query','Invalid net-symbol kind or page size.')
        if 'netSymbols' not in session:
            d=session['directory'];out=d/(new_id('net-symbols')+'.json')
            run_tcl(library.config,'inspect_net_symbols.tcl',[str(d/'library.olb'),str(out)],d);library._session(lid)
            if out.stat().st_size>16*1024*1024:raise CadenceError('output_limit','Net symbol inspection exceeds limit.')
            try:rows=symbol_rows(json.loads(out.read_text(encoding='utf-8')))
            except (ValueError,OSError) as e:raise CadenceError('invalid_worker_result','Invalid net symbol document.') from e
            session['netSymbols']=rows;session['netSymbolCursors']={};out.unlink()
        rows=[r for r in session['netSymbols'] if kind is None or r['kind']==kind];signature=(kind,limit);offset=0
        if cursor is not None:
            saved=session['netSymbolCursors'].get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Net-symbol cursor is bound to its session, kind and limit.')
            offset=saved[1]
        next_cursor=None
        if offset+limit<len(rows):
            if len(session['netSymbolCursors'])>=10000:raise CadenceError('cursor_limit','Too many symbol cursors.')
            next_cursor=new_id('net-symbol-cursor');session['netSymbolCursors'][next_cursor]=(signature,offset+limit)
        library._session(lid)
        return {'libraryId':lid,'revision':session['revision'],'scope':'library_net_symbol_definitions','identityScope':'session_revision','items':rows[offset:offset+limit],'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,'readOnly':True,'symbolGeometryVerified':False,'notChecked':['symbol_graphics_and_hotspots','placement','electrical_connectivity','embedding_closure','other_version_type_codes']}
