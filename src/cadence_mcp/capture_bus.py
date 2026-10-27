"""Bounded named bus/member and native entry-link inventory on immutable snapshots."""
import json
from .core import CadenceError,checked_path,new_id
from .environment import run_tcl

def _point(value):return isinstance(value,list) and len(value)==2 and all(type(v) is int and -(2**31)<=v<2**31 for v in value)

def validate_bus_inventory(data,pages):
    try:
        if not isinstance(data,dict) or set(data)!={'wires','entries'}:raise ValueError('shape')
        if any(not isinstance(data[k],list) for k in data):raise ValueError('arrays')
        budget=len(data['wires'])+len(data['entries']);text_bytes=0;wires={};ids=set()
        for w in data['wires']:
            if not isinstance(w,dict) or set(w)!={'wireId','pageId','isBus','isBundle','name','points','width','members'}:raise ValueError('wire shape')
            if not isinstance(w['wireId'],str) or not 1<=len(w['wireId'])<=512 or w['wireId'] in ids or w['pageId'] not in pages:raise ValueError('wire identity')
            ids.add(w['wireId']);wires[w['wireId']]=w
            if type(w['isBus']) is not bool or type(w['isBundle']) is not bool or type(w['width']) is not int or not 0<=w['width']<=10000:raise ValueError('wire type')
            if not isinstance(w['name'],str) or len(w['name'])>4096 or not isinstance(w['members'],list) or not isinstance(w['points'],list) or not 2<=len(w['points'])<=10000 or not all(_point(p) for p in w['points']):raise ValueError('wire values')
            budget+=len(w['points'])+len(w['members']);text_bytes+=len(w['name'].encode('utf-8'))
            if not w['isBus'] and (w['width']!=0 or w['members'] or w['isBundle']):raise ValueError('scalar members')
            if w['isBus'] and len(w['members'])!=w['width']:raise ValueError('member width')
            for i,m in enumerate(w['members']):
                if not isinstance(m,dict) or set(m)!={'position','name'} or type(m['position']) is not int or m['position']!=i or not isinstance(m['name'],str) or len(m['name'])>4096:raise ValueError('member')
                text_bytes+=len(m['name'].encode('utf-8'))
        for e in data['entries']:
            if not isinstance(e,dict) or set(e)!={'entryId','pageId','entryPoint','endPoint','entryWireId','endWireId'}:raise ValueError('entry shape')
            if not isinstance(e['entryId'],str) or not 1<=len(e['entryId'])<=512 or e['entryId'] in ids or e['pageId'] not in pages or not _point(e['entryPoint']) or not _point(e['endPoint']):raise ValueError('entry identity')
            ids.add(e['entryId'])
            for key in ('entryWireId','endWireId'):
                if e[key] is not None and (not isinstance(e[key],str) or e[key] not in wires or wires[e[key]]['pageId']!=e['pageId']):raise ValueError('entry link')
        if budget>100000 or text_bytes>4*1024*1024:raise ValueError('budget')
    except (KeyError,TypeError,ValueError,UnicodeError) as error:raise CadenceError('invalid_bus_inventory','Invalid or excessive native bus inventory.','decode') from error

def query_bus(capture,session_id,entity,page_id=None,cursor=None,limit=100):
    if entity=='pin_member':
        from .capture_bus_pins import query_pin_members
        return query_pin_members(capture,session_id,page_id,cursor,limit)
    if entity not in ('bus','scalar','entry') or type(limit) is not int or not 1<=limit<=1000 or (page_id is not None and not isinstance(page_id,str)):
        raise CadenceError('invalid_query','Select bus/scalar/entry and a bounded page size.')
    with capture.lock:
        session=capture._session(session_id);pages={p['objectId'] for p in session['data']['page']}
        if page_id is not None and page_id not in pages:raise CadenceError('invalid_scope','Page is outside this immutable session.')
        if 'busInventory' not in session:
            directory=checked_path(str(capture._workspace(session['workspaceId'])['directory']),(capture.config.workspace_root,));output=directory/(new_id('bus-inventory')+'.json')
            run_tcl(capture.config,'inspect_bus.tcl',[str(session['design']),str(output)],directory);capture._session(session_id)
            try:
                if not output.is_file() or output.stat().st_size>32*1024*1024:raise ValueError('size')
                data=json.loads(output.read_text(encoding='utf-8'))
            except (OSError,ValueError) as error:raise CadenceError('invalid_bus_inventory','Native bus inventory is missing or invalid.','decode') from error
            validate_bus_inventory(data,pages);output.unlink();session['busInventory']=data
        data=session['busInventory'];rows=data['entries'] if entity=='entry' else [w for w in data['wires'] if w['isBus']==(entity=='bus')]
        if page_id is not None:rows=[row for row in rows if row['pageId']==page_id]
        cursors=session.setdefault('busInventoryCursors',{});signature=(entity,page_id,limit);offset=0
        if cursor is not None:
            saved=cursors.get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Bus cursor belongs to another session/query/page size.')
            offset=saved[1]
        next_cursor=None
        if offset+limit<len(rows):
            if len(cursors)>=10000:raise CadenceError('cursor_limit','Open a new session before requesting more cursors.')
            next_cursor=new_id('bus-cursor');cursors[next_cursor]=(signature,offset+limit)
        return {'sessionId':session_id,'revision':session['revision'],'entity':entity,'items':rows[offset:offset+limit],
                'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,'scope':'design_definitions',
                'units':'capture_native_integer','entryLinkScope':'native_direct_wire_references','electricalConnectivityVerified':False,
                'notChecked':['physical_pin_member_connectivity','occurrence_bus_connectivity','nested_bundle_semantics','native_drc']}
