"""Canonical native page-net memberships; no grouping by label text."""
import json
from .core import CadenceError
from .capture_wire import point,path_key

def page_partition(rows,renamed_wire=None,expected_name=None):
    if not isinstance(rows,list) or len(rows)>100000:raise CadenceError('invalid_page_partition','Invalid bounded native net records.')
    keys=set();groups={};unbound=[];selected=[]
    for r in rows:
        common={'kind','schematicName','pageName','group','netName'}
        if not isinstance(r,dict) or r.get('kind') not in ('pin','wire'):raise CadenceError('invalid_page_partition','Invalid native row kind.')
        fields=common|({'reference','number','name'} if r['kind']=='pin' else {'nativeId','points'})
        if set(r)!=fields or any(type(r[k]) is not str or '\x00' in r[k] or len(r[k])>1024 for k in ('schematicName','pageName','netName')):raise CadenceError('invalid_page_partition','Invalid native net record fields.')
        scope=(r['schematicName'],r['pageName'])
        if r['kind']=='pin':
            if any(type(r[k]) is not str or '\x00' in r[k] or len(r[k])>512 for k in ('reference','number','name')):raise CadenceError('invalid_page_partition','Invalid pin key.')
            identity=['pin',*scope,r['reference'],r['number'],r['name']]
        else:
            if type(r['nativeId']) is not int or not isinstance(r['points'],list) or not 2<=len(r['points'])<=256 or any(not point(p) for p in r['points']):raise CadenceError('invalid_page_partition','Invalid wire key.')
            identity=['wire',*scope,path_key(r['points'])]
        key=json.dumps(identity,ensure_ascii=False,separators=(',',':'))
        if key in keys:raise CadenceError('ambiguous_page_partition','Repeated native pin/wire semantic identity.')
        keys.add(key)
        if r['group'] is None:
            if r['kind']=='wire' or r['netName']!='':raise CadenceError('invalid_page_partition','Invalid unbound metadata.')
            unbound.append(key);continue
        if type(r['group']) is not str or not r['group']:raise CadenceError('invalid_page_partition','Invalid native group.')
        g=(*scope,r['group'])
        group=groups.setdefault(g,{'name':r['netName'],'members':[]})
        if group['name']!=r['netName']:raise CadenceError('invalid_page_partition','Inconsistent native group name.')
        group['members'].append(key)
        if r['kind']=='wire' and renamed_wire and (scope[0],scope[1],r['nativeId'])==tuple(renamed_wire):selected.append(g)
    if renamed_wire and len(selected)!=1:raise CadenceError('ambiguous_page_partition','Target native wire group is not unique.')
    result=[]
    for g,row in groups.items():
        if g in selected:
            if expected_name is not None and row['name']!=expected_name:raise CadenceError('alias_owner_name_mismatch','Edited alias wire name differs from explicit expectation.')
            name='__TARGET_NATIVE_NAME__'
        else:name=row['name']
        result.append({'name':name,'members':sorted(row['members'])})
    return {'groups':sorted(result,key=lambda row:json.dumps(row,sort_keys=True,ensure_ascii=False)),'unbound':sorted(unbound)}
