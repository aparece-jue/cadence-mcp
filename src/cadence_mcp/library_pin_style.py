"""Symbol-pin flags use semantic scopes, with all native flags preserved."""
import copy,json
from .core import CadenceError,new_id
from .environment import run_tcl
from .library_semantics import library_graph

FLAGS={'long','clock','dot','leftPointing','rightPointing','netStyle','noConnect','visible','global','numberVisible','userDefinedShape'}
EDITABLE={'long','clock','dot'}

def scopes(data):
 packages={r['objectId']:r for r in data['package']};devices={r['objectId']:r for r in data['device']};cells={r['objectId']:r for r in data['cell']};parts={r['objectId']:r for r in data['part']}
 return {pin['objectId']:[packages[pin['packageId']]['name'],devices[pin['deviceId']]['designator'],devices[pin['deviceId']]['position'],cells[parts[pin['partId']]['cellId']]['name'],parts[pin['partId']]['name'],pin['position']] for pin in data['pin']}

def validate_style(style):
 if not isinstance(style,dict) or not style or not set(style)<=EDITABLE or any(type(v) is not bool for v in style.values()):
  raise CadenceError('invalid_pin_style','Declare explicit boolean long, clock and/or dot fields.')
 return copy.deepcopy(style)

def normalize_styles(raw,bound):
 try:
  data={k:v for k,v in raw.items() if k!='pinStyles'}
  if library_graph(data)!=library_graph(bound):raise CadenceError('target_changed','Pin style definitions differ from the library revision.')
  keys=scopes(data);rows=raw['pinStyles'];seen=set();result=[]
  if not isinstance(rows,list) or len(rows)!=len(keys) or len(rows)>8192:raise ValueError('coverage')
  for row in rows:
   if not isinstance(row,dict) or set(row)!={'pinId','flags'} or row['pinId'] not in keys or row['pinId'] in seen or set(row['flags'])!=FLAGS or any(type(v) is not bool for v in row['flags'].values()):raise ValueError('flags')
   seen.add(row['pinId']);result.append({'scope':keys[row['pinId']],'flags':copy.deepcopy(row['flags'])})
  return sorted(result,key=lambda r:json.dumps(r['scope'],ensure_ascii=False))
 except (KeyError,TypeError,ValueError,AttributeError) as error:raise CadenceError('invalid_pin_style_result','Every pin needs one complete bounded native flag row.','decode') from error

def read_styles(config,source,directory,data):
 output=directory/(new_id('pin-style')+'.json');run_tcl(config,'inspect_library_pin_styles.tcl',[str(source),str(output),'100000'],directory)
 if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Pin style graph exceeds32MiB.')
 result=normalize_styles(json.loads(output.read_text(encoding='utf-8')),data);output.unlink();return result

def expected_styles(rows,scope,style,visible=None,source_pin_type=None,pin_type=None):
 if visible is not None and type(visible) is not bool:raise CadenceError('invalid_pin_style','Visibility must be boolean.')
 if pin_type is not None and (type(pin_type) is not int or pin_type not in range(8)):raise CadenceError('invalid_pin_style','Invalid edited pin type.')
 style=validate_style(style);expected=copy.deepcopy(rows);changes=[];old=[]
 for row in expected:
  if row['scope'][3:]!=scope[3:]:continue
  before=copy.deepcopy(row['flags']);old.append(before)
  row['flags'].update(style)
  if visible is not None:row['flags']['visible']=visible
  if (visible is not None and visible!=before['visible']) or (pin_type is not None and pin_type!=source_pin_type):
   if type(source_pin_type) is not int or source_pin_type not in range(8):raise CadenceError('invalid_pin_style','The original pin type is required for derived global semantics.')
   effective_type=source_pin_type if pin_type is None else pin_type
   row['flags']['global']=effective_type==7 or not row['flags']['visible']
  if row['flags']!=before:changes.append({'scope':copy.deepcopy(row['scope']),'old':before,'expected':copy.deepcopy(row['flags'])})
 if not old or any(v!=old[0] for v in old):raise CadenceError('ambiguous_pin_style','Shared symbol flag definitions must agree.')
 if len(changes)>64:raise CadenceError('affected_limit','More than64 shared pin-style view rows would change.')
 return expected,changes,old[0]

def query_style(library,library_id,pin_id):
 with library.lock:
  session=library._session(library_id);keys=scopes(session['data'])
  if pin_id not in keys:raise CadenceError('object_not_found','Pin is outside this library revision.')
  rows=read_styles(library.config,session['directory']/'library.olb',session['directory'],session['data']);library._session(library_id);scope=keys[pin_id];target=next(r for r in rows if r['scope']==scope)
  return {'libraryId':library_id,'revision':session['revision'],'pinId':pin_id,'scope':scope,'flags':target['flags'],'sharedViewScopes':[r['scope'] for r in rows if r['scope'][3:]==scope[3:]],'readOnly':True,'notChecked':['rendered_pin_shape','dsn_cache_or_instances','electrical_behavior']}
