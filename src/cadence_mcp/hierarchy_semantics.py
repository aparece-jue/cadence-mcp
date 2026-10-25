"""Native flat-object partitions with explicit occurrence and physical pin identity."""
import json
from .core import CadenceError

def native_partition_rows(pins):
    """Decode the fixed Tcl reader's native integer GetIsGlobal flag explicitly."""
    if not isinstance(pins,list) or len(pins)>100000:raise CadenceError('invalid_flat_partition','Invalid native pin table.')
    result=[]
    for pin in pins:
        if not isinstance(pin,dict):raise CadenceError('invalid_flat_partition','Invalid native pin record.')
        row=dict(pin)
        if type(row.get('isGlobal')) is int and row['isGlobal'] in (0,1):row['isGlobal']=bool(row['isGlobal'])
        result.append(row)
    net_partition(result)
    return result

def net_partition(pins, *, include_private_names=True):
    if not isinstance(pins,list) or len(pins)>100000:
        raise CadenceError('invalid_flat_partition','Invalid bounded native pin table.')
    groups={};unbound=[];identities=set()
    for pin in pins:
        if not isinstance(pin,dict):raise CadenceError('invalid_flat_partition','Invalid pin record.')
        try:path=pin['instancePathSegments'];name=pin['name'];number=pin['occurrencePhysicalNumber'];flat=pin['flatNetId'];netname=pin['flatNetName'];glob=pin['isGlobal']
        except KeyError as e:raise CadenceError('invalid_flat_partition','Missing native partition field.') from e
        if not isinstance(path,list) or not 1<=len(path)<=64 or any(type(s) is not str or not s or len(s)>512 or '\x00' in s for s in path):raise CadenceError('invalid_flat_partition','Invalid occurrence segments.')
        if type(name) is not str or len(name)>512 or '\x00' in name or (number is not None and (type(number) is not str or len(number)>512 or '\x00' in number)) or type(netname) is not str:
            raise CadenceError('invalid_flat_partition','Invalid pin or net identity.')
        key=json.dumps([path,name,number],ensure_ascii=False,separators=(',',':'))
        if key in identities:raise CadenceError('ambiguous_flat_pin','Duplicate occurrence physical pin identity.')
        identities.add(key)
        if flat is None:
            if glob is not None or netname!='':raise CadenceError('invalid_flat_partition','Unbound row cannot claim native global/net identity.')
            unbound.append(key);continue
        if type(flat) is not str or not flat or len(flat)>512 or type(glob) is not bool:
            raise CadenceError('invalid_flat_partition','Invalid native flat object identity.')
        metadata=(netname,glob)
        if flat in groups and groups[flat]['metadata']!=metadata:raise CadenceError('invalid_flat_partition','One native flat object has inconsistent metadata.')
        group=groups.setdefault(flat,{'metadata':metadata,'pins':[]});group['pins'].append(key)
    rows=[]
    for group in groups.values():
        name,glob=group['metadata'];rows.append({'pins':sorted(group['pins']),'isGlobal':glob,'name':name if include_private_names or glob else None})
    return {'groups':sorted(rows,key=lambda row:json.dumps(row,sort_keys=True,ensure_ascii=False)),'unbound':sorted(unbound)}

def verify_reused_context(before,after,source_context,added_context,shared_globals):
    # Validate the entire tables before selecting a domain, so duplicate/invalid
    # rows cannot disappear through filtering.
    net_partition(before);net_partition(after)
    if source_context==added_context or not source_context or not added_context:
        raise CadenceError('invalid_clone_context','Source and new occurrence contexts must differ.')
    if any(p['instancePathSegments'][0]==added_context for p in before):raise CadenceError('invalid_clone_context','New context already existed.')
    old=[p for p in after if p['instancePathSegments'][0]!=added_context]
    if net_partition(before)!=net_partition(old):raise CadenceError('hierarchy_original_partition_changed','Original physical pin partition or flat metadata changed.')
    original=[p for p in after if len(p['instancePathSegments'])>1 and p['instancePathSegments'][0]==source_context]
    clone=[p for p in after if len(p['instancePathSegments'])>1 and p['instancePathSegments'][0]==added_context]
    if not original or not clone:raise CadenceError('missing_clone_context','Source or cloned child pin domain is empty.')
    def normalized(rows):return [{**p,'instancePathSegments':['CHILD',*p['instancePathSegments'][1:]]} for p in rows]
    if net_partition(normalized(original),include_private_names=False)!=net_partition(normalized(clone),include_private_names=False):
        raise CadenceError('hierarchy_clone_partition_changed','Cloned child physical pin partition differs from its source context.')
    old_ids={p['flatNetId'] for p in old if p['flatNetId'] is not None};shared=[]
    for pin in clone:
        if pin['flatNetId'] in old_ids:
            if not pin['isGlobal'] or pin['flatNetName'] not in shared_globals:raise CadenceError('hierarchy_private_net_merged','A cloned private flat object merged with an original context.')
            shared.append(pin['flatNetName'])
    return {'originalPartitionPreserved':True,'childPartitionCopied':True,'privateNetsIsolated':True,'clonedChildPinCount':len(clone),'sharedGlobalNames':sorted(set(shared))}
