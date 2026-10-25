"""Part-variant aware semantic oracles, including unit counts independent of view counts."""
from cadence_mcp.core import CadenceError
from cadence_mcp.library import validate_library
from cadence_mcp.library_create import canonical_meta,sortrows

def expected_variants(spec):
 devices=[];pins=[];metas=[]
 for dev in spec['devices']:
  mapping={p['position']:p for p in dev['mapping']}
  for sym in (s for s in spec['symbols'] if s['cellName']==dev['cellName']):
   scope=[spec['packageName'],dev['designator'],dev['position'],sym['cellName'],sym['partName']];devices.append(scope)
   for pin in sym['pins']:
    physical=mapping[pin['position']];pins.append([*scope,pin['position'],physical['number'],pin['name'],pin['pinType'],pin['visible'],physical['shared'],physical['swapId'],pin['hotSpot']])
   metas.append({'scope':scope,'pinStarts':[{'position':p['position'],'start':p['start']} for p in sym['pins']],'lines':sym['lines'],'otherVectorTypes':[]})
 return {'package':{'name':spec['packageName'],'size':len(spec['devices']),'homogeneous':spec['expectedHomogeneous'],'footprint':spec['footprint']},'devices':sortrows(devices),'pins':sortrows(pins),'meta':canonical_meta({'packages':[{'packageName':spec['packageName'],'referenceTemplate':spec['referenceTemplate']}],'symbols':metas})}

def actual_variants(data):
 base={k:v for k,v in data.items() if k!='meta'};validate_library(base)
 if len(base['package'])!=1 or len(base['cell'])!=len(base['device']):raise CadenceError('unexpected_library_graph','Unexpected device/cell counts.')
 package={k:v for k,v in base['package'][0].items() if k!='objectId'};cells={r['objectId']:r for r in base['cell']};devices=[];pins=[];seen=set()
 for dev in base['device']:
  cell=cells[dev['cellId']];parts=[p for p in base['part'] if p['cellId']==cell['objectId']]
  if not 1<=len(parts)<=16 or len({p['name'].casefold() for p in parts})!=len(parts):raise CadenceError('unexpected_library_graph','Missing/duplicate/bounded part variants.')
  for part in parts:
   seen.add(part['objectId']);scope=[package['name'],dev['designator'],dev['position'],cell['name'],part['name']];devices.append(scope)
   for pin in (p for p in base['pin'] if p['partId']==part['objectId']):pins.append([*scope,pin['position'],pin['number'],pin['name'],pin['pinType'],pin['visible'],pin['shared'],pin['swapId'],pin['hotSpot']])
 if len(seen)!=len(base['part']):raise CadenceError('unexpected_library_graph','Unmatched declared part variant.')
 return {'package':package,'devices':sortrows(devices),'pins':sortrows(pins),'meta':canonical_meta(data['meta'])}
