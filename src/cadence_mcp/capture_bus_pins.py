"""Native definition-pin bus membership; no geometry or string-based membership inference."""
import json
from .core import CadenceError,checked_path,new_id
from .environment import run_tcl

def validate_pin_members(data,definitions):
    try:
        if not isinstance(data,dict) or set(data)!=set(definitions)|{'busGroups','memberships'}:raise ValueError('shape')
        for kind,expected in definitions.items():
            rows=data[kind]
            if not isinstance(rows,list) or rows!=[{k:v for k,v in row.items() if k!='generation'} for row in expected]:raise ValueError('definitions changed')
        groups=data['busGroups'];rows=data['memberships']
        if not isinstance(groups,list) or not isinstance(rows,list) or len(groups)+len(rows)>100000:raise ValueError('budget')
        pages={p['objectId'] for p in definitions['page']};pins={p['objectId']:p for p in definitions['pin']};by_group={};budget=len(groups)+len(rows);names=0
        for group in groups:
            if not isinstance(group,dict) or set(group)!={'busGroupId','pageId','name','width','members'}:raise ValueError('group shape')
            gid=group['busGroupId']
            if not isinstance(gid,str) or not 1<=len(gid)<=512 or gid in by_group or group['pageId'] not in pages:raise ValueError('group identity')
            if type(group['width']) is not int or not 0<=group['width']<=10000 or not isinstance(group['members'],list) or group['width']!=len(group['members']):raise ValueError('members')
            for name in [group['name'],*group['members']]:
                if not isinstance(name,str) or len(name)>4096:raise ValueError('name')
                names+=len(name.encode('utf-8'))
            budget+=group['width'];by_group[gid]=group
        page_counts={page:0 for page in pages}
        for pin in pins.values():page_counts[pin['pageId']]+=1
        expected_count=sum(page_counts[g['pageId']] for g in groups)
        if expected_count>100000 or len(rows)!=expected_count:raise ValueError('coverage')
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'pinId','busGroupId','pageId','reference','pinNumber','busName','pinNet','hasMember','position','memberPointerEqualsPinNet'}:raise ValueError('row shape')
            key=(row['pinId'],row['busGroupId'])
            if key in seen or row['pinId'] not in pins or row['busGroupId'] not in by_group:raise ValueError('row identity')
            seen.add(key);pin=pins[row['pinId']];group=by_group[row['busGroupId']]
            if row['pageId']!=pin['pageId'] or row['pageId']!=group['pageId'] or row['reference']!=pin['reference'] or row['pinNumber']!=pin['number'] or row['pinNet']!=pin['net'] or row['busName']!=group['name']:raise ValueError('row scope')
            if type(row['hasMember']) is not bool or type(row['memberPointerEqualsPinNet']) is not bool or type(row['position']) is not int or row['hasMember']!=row['memberPointerEqualsPinNet']:raise ValueError('membership proof')
            if row['hasMember']:
                if not pin['connected'] or not 0<=row['position']<group['width'] or group['members'][row['position']]!=pin['net']:raise ValueError('member position')
            elif row['position']!=-1:raise ValueError('nonmember position')
            names+=sum(len(row[k].encode('utf-8')) for k in ('reference','pinNumber','busName','pinNet'))
        if budget>100000 or names>4194304:raise ValueError('budget')
    except (KeyError,TypeError,ValueError,UnicodeError) as error:raise CadenceError('invalid_bus_pin_inventory','Invalid, incomplete or excessive native bus pin membership.','decode') from error

def query_pin_members(capture,session_id,page_id=None,cursor=None,limit=100):
    if type(limit) is not int or not 1<=limit<=1000 or (page_id is not None and not isinstance(page_id,str)):raise CadenceError('invalid_query','Use a bounded page size and exact optional page.')
    with capture.lock:
        session=capture._session(session_id);pages={p['objectId'] for p in session['data']['page']}
        if page_id is not None and page_id not in pages:raise CadenceError('invalid_scope','Page is outside this session.')
        if 'busPinInventory' not in session:
            directory=checked_path(str(capture._workspace(session['workspaceId'])['directory']),(capture.config.workspace_root,));output=directory/(new_id('bus-pin-inventory')+'.json')
            run_tcl(capture.config,'inspect_bus_pin_members.tcl',[str(session['design']),str(output),'100000'],directory);capture._session(session_id)
            try:
                if not output.is_file() or output.stat().st_size>32*1024*1024:raise ValueError('size')
                data=json.loads(output.read_text(encoding='utf-8'))
            except (OSError,ValueError) as error:raise CadenceError('invalid_bus_pin_inventory','Missing or invalid bus pin inventory.','decode') from error
            validate_pin_members(data,session['data']);session['busPinInventory']=data;output.unlink()
        data=session['busPinInventory'];rows=[row for row in data['memberships'] if page_id is None or row['pageId']==page_id]
        cursors=session.setdefault('busPinCursors',{});signature=(page_id,limit);offset=0
        if cursor is not None:
            saved=cursors.get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Bus pin cursor belongs to another session/query/page size.')
            offset=saved[1]
        next_cursor=None
        if offset+limit<len(rows):
            if len(cursors)>=10000:raise CadenceError('cursor_limit','Open a new session before requesting more cursors.')
            next_cursor=new_id('bus-pin-cursor');cursors[next_cursor]=(signature,offset+limit)
        return dict(sessionId=session_id,revision=session['revision'],entity='pin_member',items=rows[offset:offset+limit],total=len(rows),nextCursor=next_cursor,complete=next_cursor is None,scope='same_page_design_definition_native_net_membership',membershipMethod='HasMember/GetPosition/GetMember_pointer_identity',electricalConnectivityVerified=False,notChecked=['occurrence_bus_connectivity','routing_completeness','nested_bundle_semantics','native_drc'])
