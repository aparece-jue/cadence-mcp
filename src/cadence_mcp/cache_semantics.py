"""Exact effective-property comparison independent of native enumeration order."""
from .core import CadenceError

def effective_property_snapshot(document):
    keys={'partId','schematicName','pageName','reference','properties'}
    if not isinstance(document,dict) or set(document)!=keys or any(type(document[k]) is not str for k in keys-{'properties'}):
        raise CadenceError('invalid_property_snapshot','Invalid qualified instance property snapshot.')
    rows=document['properties']
    if not isinstance(rows,list) or len(rows)>10000:raise CadenceError('invalid_property_snapshot','Invalid bounded property list.')
    seen=set();canonical=[]
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'name','value'} or any(type(row[k]) is not str for k in ('name','value')):
            raise CadenceError('invalid_property_snapshot','Invalid exact property record.')
        if row['name'] in seen:raise CadenceError('ambiguous_property_snapshot','Duplicate property names require explicit resolution.')
        seen.add(row['name']);canonical.append(dict(row))
    return {**document,'properties':sorted(canonical,key=lambda row:row['name'])}
