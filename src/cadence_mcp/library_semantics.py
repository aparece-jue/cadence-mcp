"""Canonical OLB graph preserving device/variant/pin semantics, excluding ordinals."""
import json
from .library import validate_library
from .core import CadenceError

def library_graph(data):
    validate_library(data)
    packages={r['objectId']:r for r in data['package']};devices={r['objectId']:r for r in data['device']}
    cells={r['objectId']:r for r in data['cell']};parts={r['objectId']:r for r in data['part']}
    result={key:[] for key in data};keys={key:set() for key in data}
    def device_scope(row):
        d=devices[row['deviceId']]
        return [packages[d['packageId']]['name'],d['designator'],d['position']]
    def add(kind,key,row):
        identity=json.dumps(key,ensure_ascii=False,separators=(',',':'))
        if identity in keys[kind]:raise CadenceError('ambiguous_library_graph','Duplicate semantic OLB identity requires a more specific operation.')
        keys[kind].add(identity);result[kind].append(row)
    for r in data['package']:add('package',[r['name'].casefold()],{k:v for k,v in r.items() if k!='objectId'})
    for r in data['device']:
        scope=[packages[r['packageId']]['name'],r['designator'],r['position']]
        add('device',scope,{'scope':scope,'cellName':cells[r['cellId']]['name']})
    for r in data['cell']:
        scope=device_scope(r)+[r['name']];add('cell',scope,{'scope':scope})
    for r in data['part']:
        scope=device_scope(r)+[cells[r['cellId']]['name'],r['name']];add('part',scope,{'scope':scope})
    for r in data['pin']:
        part=parts[r['partId']];scope=device_scope(r)+[cells[part['cellId']]['name'],part['name'],r['position']]
        add('pin',scope,{'scope':scope,**{k:r[k] for k in ('name','number','pinType','visible','shared','swapId','hotSpot')}})
    return {kind:sorted(rows,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)) for kind,rows in result.items()}
