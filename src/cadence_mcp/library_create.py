"""Declared single-package OLB construction, including device/symbol pin maps."""
import copy,json,re
from pathlib import Path
from datetime import datetime,timezone
from .core import CadenceError,Config,checked_path,sha256,write_json,new_id
from .isolated_jobs import IsolatedJobs,digest
from .environment import ADAPTERS,run_tcl,process_env
from .process_tree import run_owned_process
from .library import LibraryService,validate_library
from .library_vectors import validate_vectors,vector_descriptor,declared_descriptor
from .bitmap_assets import freeze_assets,verify_assets

def point(p):return isinstance(p,list) and len(p)==2 and all(type(v) is int and abs(v)<=1000000 for v in p)
def label(v):return isinstance(v,str) and 1<=len(v)<=64 and re.fullmatch(r'\w[\w .-]*',v) is not None and v.strip(' .')==v
def sortrows(rows):return sorted(rows,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))

def packages(spec):
    return spec['packages'] if set(spec)=={'packages'} else [spec]

def physical_pad_count(spec):
    return sum(len({m['number'] for d in p['devices'] for m in d['mapping']}) for p in packages(spec))

def creation_assets(config,spec,freeze=False):
    if set(spec)=={'packages'}:
        return {'packages':[creation_assets(config,p,freeze) for p in spec['packages']]}
    if freeze:return freeze_assets(config,spec)
    verify_assets(config,spec)

def validate_family(spec):
    try:
        if not isinstance(spec['packages'],list) or not 2<=len(spec['packages'])<=8:raise ValueError()
        names=set();cells=set();parts=set();symbols=devices=pins=maps=0;items=[]
        for item in spec['packages']:
            if not isinstance(item,dict) or 'packages' in item:raise ValueError()
            item=validate_spec(item);name=item['packageName'].casefold()
            own_cells={s['cellName'].casefold() for s in item['symbols']};own_parts={s['partName'].casefold() for s in item['symbols']}
            if name in names or cells & own_cells or parts & own_parts:raise ValueError()
            names.add(name);cells.update(own_cells);parts.update(own_parts);items.append(item)
            symbols+=len(item['symbols']);devices+=len(item['devices']);pins+=sum(len(s['pins']) for s in item['symbols']);maps+=sum(len(d['mapping']) for d in item['devices'])
        bitmaps=[v for p in items for s in p['symbols'] for v in s.get('vectors',[]) if v['kind']=='bitmap']
        bitmap_bytes=sum(v['expectedDibSize'] for p in items for s in p['symbols'] for v in s.get('vectors',[]) if v['kind']=='bitmap' for d in p['devices'] if d['cellName']==s['cellName'])
        if symbols>16 or devices>16 or pins>512 or maps>2048 or len(bitmaps)>32 or bitmap_bytes>64*1024*1024 or len(json.dumps(items,ensure_ascii=False).encode('utf-8'))>31000:raise ValueError()
        return {'packages':items}
    except (TypeError,KeyError,ValueError,AttributeError) as error:raise CadenceError('invalid_library_spec','Provide 2..8 packages with distinct package/cell/part namespaces and bounded independent physical maps.') from error

def validate_spec(spec):
    spec=copy.deepcopy(spec)
    if isinstance(spec,dict) and set(spec)=={'packages'}:return validate_family(spec)
    try:
        if not isinstance(spec,dict) or set(spec)!={'packageName','referenceTemplate','footprint','expectedHomogeneous','symbols','devices'}:raise ValueError()
        if not label(spec['packageName']) or not isinstance(spec['referenceTemplate'],str) or not re.fullmatch(r'[A-Za-z]{1,8}\??',spec['referenceTemplate']):raise ValueError()
        if not isinstance(spec['footprint'],str) or len(spec['footprint'])>256 or any(c in spec['footprint'] for c in '\x00\r\n') or type(spec['expectedHomogeneous']) is not bool:raise ValueError()
        if not isinstance(spec['symbols'],list) or not 1<=len(spec['symbols'])<=16 or not isinstance(spec['devices'],list) or not 1<=len(spec['devices'])<=16:raise ValueError()
        cells={};variants={};parts=set();pin_total=0
        for sym in spec['symbols']:
            if set(sym) not in ({'cellName','partName','pins','lines'},{'cellName','partName','pins','lines','vectors'}) or not label(sym['cellName']) or not label(sym['partName']):raise ValueError()
            if sym['partName'].casefold() in parts:raise ValueError()
            key=sym['cellName'].casefold()
            if key in cells and cells[key]['cellName']!=sym['cellName']:raise ValueError()
            cells.setdefault(key,sym);variants.setdefault(key,[]).append(sym);parts.add(sym['partName'].casefold())
            if not isinstance(sym['pins'],list) or not 1<=len(sym['pins'])<=256 or not isinstance(sym['lines'],list) or len(sym['lines'])>256:raise ValueError()
            if 'vectors' in sym:sym['vectors']=validate_vectors(sym['vectors'],allow_bitmaps=True)
            positions=set();pin_total+=len(sym['pins'])
            for pin in sym['pins']:
                if set(pin)!={'position','name','pinType','start','hotSpot','visible'}:raise ValueError()
                if type(pin['position']) is not int or not 0<=pin['position']<=4095 or pin['position'] in positions:raise ValueError()
                positions.add(pin['position'])
                if not isinstance(pin['name'],str) or len(pin['name'])>128 or any(c in pin['name'] for c in '\x00\r\n') or type(pin['pinType']) is not int or not 0<=pin['pinType']<8 or not point(pin['start']) or not point(pin['hotSpot']) or type(pin['visible']) is not bool:raise ValueError()
            for line in sym['lines']:
                if set(line)!={'start','end','style','width'} or not point(line['start']) or not point(line['end']) or line['start']==line['end']:raise ValueError()
                if type(line['style']) is not int or not 0<=line['style']<=4 or type(line['width']) is not int or not 0<=line['width']<=2:raise ValueError()
        if pin_total>512:raise ValueError()
        for group in variants.values():
            functions=[sorted((p['position'],p['name'],p['pinType']) for p in sym['pins']) for sym in group]
            if any(f!=functions[0] for f in functions[1:]):raise ValueError()

        device_positions=set();designators=set();used=set();pads={};map_total=0
        for dev in spec['devices']:
            if set(dev)!={'designator','position','cellName','mapping'} or not isinstance(dev['designator'],str) or not re.fullmatch(r'[A-Za-z0-9]{0,8}',dev['designator']):raise ValueError()
            if dev['designator'].casefold() in designators or type(dev['position']) is not int or dev['position'] in device_positions or not isinstance(dev['cellName'],str):raise ValueError()
            designators.add(dev['designator'].casefold());device_positions.add(dev['position']);used.add(dev['cellName'].casefold())
            sym=cells[dev['cellName'].casefold()]
            if sym['cellName']!=dev['cellName'] or not isinstance(dev['mapping'],list):raise ValueError()
            geom={p['position']:p for p in sym['pins']};mapping={};numbers=set();map_total+=len(dev['mapping'])
            for pin in dev['mapping']:
                if set(pin)!={'position','number','shared','swapId'} or type(pin['position']) is not int or pin['position'] in mapping or pin['position'] not in geom:raise ValueError()
                if not isinstance(pin['number'],str) or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,32}',pin['number']) or pin['number'] in numbers:raise ValueError()
                if type(pin['shared']) is not bool or type(pin['swapId']) is not int or not -1<=pin['swapId']<=126:raise ValueError()
                mapping[pin['position']]=pin;numbers.add(pin['number']);g=geom[pin['position']]
                pads.setdefault(pin['number'],[]).append((pin['shared'],g['name'],g['pinType'],pin['swapId']))
            if set(mapping)!=set(geom):raise ValueError()
        if used!=set(cells) or device_positions!=set(range(len(spec['devices']))) or map_total>2048:raise ValueError()
        for entries in pads.values():
            if len(entries)>1 and (not all(v[0] for v in entries) or len({v[1:] for v in entries})!=1):raise ValueError()
        if len(json.dumps(spec,ensure_ascii=False).encode('utf-8'))>32000:raise ValueError()
    except (TypeError,KeyError,ValueError,AttributeError) as error:raise CadenceError('invalid_library_spec','Provide a bounded consistent package/symbol/device/physical-pin specification.') from error
    return copy.deepcopy(spec)

def canonical_meta(meta,native=False):
    if not isinstance(meta,dict) or set(meta)!={'packages','symbols'}:raise CadenceError('invalid_library_metadata','Unexpected library metadata shape.')
    symbols=[]
    for row in meta['symbols']:
        if set(row) not in ({'scope','pinStarts','lines','otherVectorTypes'},{'scope','pinStarts','lines','otherVectorTypes','orderedVectors'}) or row['otherVectorTypes']:raise CadenceError('unexpected_library_vectors','New library contains undeclared vector types.')
        lines=[]
        for line in row['lines']:
            if set(line)!={'start','end','style','width'} or not point(line['start']) or not point(line['end']):raise CadenceError('invalid_library_metadata','Malformed line metadata.')
            lines.append({'ends':sorted([line['start'],line['end']]),'style':line['style'],'width':line['width']})
        symbol={'scope':row['scope'],'pinStarts':sortrows(row['pinStarts']),'lines':sortrows(lines)}
        if 'orderedVectors' in row:
            if not isinstance(row['orderedVectors'],list) or len(row['orderedVectors'])>512:raise CadenceError('invalid_library_metadata','Invalid ordered vectors.')
            symbol['orderedVectors']=[declared_descriptor(v) if native else v for v in row['orderedVectors']]
        symbols.append(symbol)
    return {'packages':sortrows(meta['packages']),'symbols':sortrows(symbols)}

def expected_graph(spec,ordered=None):
 if set(spec)=={'packages'}:
  ordered=any(s.get('vectors') for p in spec['packages'] for s in p['symbols'])
  return {'packages':sortrows([expected_graph(p,ordered) for p in spec['packages']])}
 devices=[];pins=[];metas=[];ordered=any(s.get('vectors') for s in spec['symbols']) if ordered is None else ordered
 for dev in spec['devices']:
  mapping={p['position']:p for p in dev['mapping']}
  for sym in (s for s in spec['symbols'] if s['cellName']==dev['cellName']):
   scope=[spec['packageName'],dev['designator'],dev['position'],sym['cellName'],sym['partName']];devices.append(scope)
   for pin in sym['pins']:
    physical=mapping[pin['position']];pins.append([*scope,pin['position'],physical['number'],pin['name'],pin['pinType'],pin['visible'],physical['shared'],physical['swapId'],pin['hotSpot']])
   meta={'scope':scope,'pinStarts':[{'position':p['position'],'start':p['start']} for p in sym['pins']],'lines':sym['lines']+[{k:v for k,v in vector.items() if k!='kind'} for vector in sym.get('vectors',[]) if vector['kind']=='line'],'otherVectorTypes':[]}
   if ordered:meta['orderedVectors']=[vector_descriptor({'kind':'line',**line}) for line in sym['lines']]+[vector_descriptor(v) for v in sym.get('vectors',[])]
   metas.append(meta)
 return {'package':{'name':spec['packageName'],'size':len(spec['devices']),'homogeneous':spec['expectedHomogeneous'],'footprint':spec['footprint']},'devices':sortrows(devices),'pins':sortrows(pins),'meta':canonical_meta({'packages':[{'packageName':spec['packageName'],'referenceTemplate':spec['referenceTemplate']}],'symbols':metas})}

def actual_graph(data,family=False):
 if family:
  validate_library({k:v for k,v in data.items() if k!='meta'})
  meta=data['meta'];names={p['name'] for p in data['package']}
  if set(meta)!={'packages','symbols'} or any(m['packageName'] not in names for m in meta['packages']) or any(m['scope'][0] not in names for m in meta['symbols']):raise CadenceError('unexpected_library_graph','Unmatched family metadata.')
  graphs=[]
  for package in data['package']:
   subset={'package':[package],**{k:[row for row in data[k] if row['packageId']==package['objectId']] for k in ('device','cell','part','pin')}}
   subset['meta']={'packages':[m for m in meta['packages'] if m['packageName']==package['name']],'symbols':[m for m in meta['symbols'] if m['scope'][0]==package['name']]}
   graphs.append(actual_graph(subset))
  return {'packages':sortrows(graphs)}
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
 return {'package':package,'devices':sortrows(devices),'pins':sortrows(pins),'meta':canonical_meta(data['meta'],native=True)}

class LibraryCreates(IsolatedJobs):
    kind='capture_library_create'
    def __init__(self,config,library):super().__init__(config);self.library=library
    def plan(self,spec):
        spec=validate_spec(creation_assets(self.config,validate_spec(spec),True));return self.create_plan({'spec':spec,'specDigest':digest(spec),'expectedGraphDigest':digest(expected_graph(spec))})
    def preview(self,p):return {'operation':'create_new_library','spec':p['spec'],'specDigest':p['specDigest'],'sourceKind':'new_library_spec','uniquePhysicalPadCount':physical_pad_count(p['spec'])}
    def preflight(self,p):
        spec=validate_spec(p['spec'])
        creation_assets(self.config,spec)
        if digest(spec)!=p['specDigest'] or digest(expected_graph(spec))!=p['expectedGraphDigest']:raise CadenceError('invalid_plan','Library specification or semantic expectation changed.')
    def execute(self,directory,p,cancel,on_started):
        self.preflight(p);write_json(directory/'spec.json',p['spec'])
        if (directory/'library.olb').exists():raise CadenceError('output_exists','Do not overwrite an existing OLB.')
        return run_owned_process(self.native_command(directory,p),directory,process_env(self.config),self.config.timeout_seconds,cancel=cancel,on_started=on_started)
    def native_command(self,directory,p):return [str(x) for x in [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'create_library.tcl',self.config.install_root,directory/'spec.json',directory/'library.olb',directory/'native-result.json']]
    def verify(self,directory,p,native_completed):
        self.preflight(p);target=checked_path(str(directory/'library.olb'),(directory,));before=sha256(target)
        if target.stat().st_size>128*1024*1024:raise CadenceError('output_limit','New OLB exceeds bound.')
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':'create_library'}:raise CadenceError('invalid_worker_result','New OLB save receipt differs.')
        output=directory/(new_id('library-verify')+'.json');run_tcl(self.config,'inspect_library_create.tcl',[str(target),str(output),'100000',str(int(any(s.get('vectors') for pkg in packages(p['spec']) for s in pkg['symbols'])))],directory)
        if output.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Library verification exceeds bound.')
        try:data=json.loads(output.read_text(encoding='utf-8'));actual=actual_graph(data,family=set(p['spec'])=={'packages'})
        except (ValueError,TypeError,KeyError) as error:raise CadenceError('invalid_library_metadata','Invalid independent OLB metadata.') from error
        if digest(actual)!=p['expectedGraphDigest']:raise CadenceError('library_creation_mismatch','Saved OLB graph/pin mapping/template/geometry differs from the declared specification.','verify')
        if sha256(target)!=before:raise CadenceError('target_changed','New OLB changed while independently reading.')
        ident=directory.name.removeprefix('plan-');artifact={'artifactId':'library-'+ident,'kind':'capture_created_library','workspaceRelativePath':'library.olb','sha256':before,'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':p['specDigest'],'sourceKind':'new_library_spec','createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,'sourceKind':'new_library_spec','sourceModified':False,'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'declaredGraphVerified':True,'uniquePhysicalPadCount':physical_pad_count(p['spec']),'notChecked':['rendered_labels_fonts','other_vector_types','electrical_simulation_model','native_drc','external_footprint_exists']}
    def open_output(self,plan_id,plan_digest):
        guard=self._guard()
        try:
            directory,_,row=self._load(plan_id)
            if row['digest']!=plan_digest:raise CadenceError('plan_digest_mismatch','Plan digest differs.')
            if row['state'] not in ('verified','verified_recovered'):raise CadenceError('output_unverified','Only independently verified OLB output can be opened.')
            result=self._verified_result(directory,row)
            with self.library.lock:
                if len(self.library.sessions)>=32:raise CadenceError('session_limit','Close a library session first.')
                internal=LibraryService(Config(self.config.install_root,self.config.workspace_root,(directory,),self.config.timeout_seconds));opened=internal.open(str(directory/'library.olb'));ident=opened['libraryId']
                self.library.sessions[ident]=internal.sessions.pop(ident)
                return opened|{'producedByPlan':plan_id,'creationSpecDigest':result['artifact']['sourceFingerprint']}
        finally:guard.close()
