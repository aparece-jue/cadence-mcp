"""Source-bound global/offpage creation with explicit hotspot and pin oracles."""
import copy,json,re
from .capture import CaptureService
from .capture_part_edit import CapturePartEdits,page_geometry
from .capture_wire import inventory,connection_digest,expected_definitions,point,path_key
from .capture_edit import definition_baseline
from .capture_references import read_units
from .net_symbols import query_net_symbols
from .core import CadenceError,checked_path,sha256,new_id,write_json
from .environment import ADAPTERS,run_tcl

def symbol_expectation(objects,page_id,kind,name,cache,location,hotspot,rotation,mirror,lead_end):
    if kind not in ('global','offpage'):raise CadenceError('unsupported_net_symbol_kind','Only global/offpage symbol creation is implemented.')
    if not isinstance(name,str) or not re.fullmatch(r'[^\s\[\]\x00-\x1f\x7f]{1,128}',name):raise CadenceError('invalid_net_symbol_name','Use a bounded scalar net identifier.')
    if not point(location) or not point(hotspot) or type(rotation) is not int or rotation not in range(4) or type(mirror) is not int or mirror not in (0,1):raise CadenceError('invalid_net_symbol_pose','Use bounded integer origin/hotspot, rotation0..3 and mirror0/1.')
    if lead_end is not None and (not point(lead_end) or lead_end==hotspot or (lead_end[0]!=hotspot[0] and lead_end[1]!=hotspot[1])):raise CadenceError('invalid_lead','Lead endpoints must be distinct and orthogonal.')
    if any(o['kind']==kind and o['pageId']==page_id and o['attributes']['name']==name and o['attributes']['location']==location for o in objects):raise CadenceError('net_symbol_conflict','A matching symbol instance already exists.')
    if lead_end is not None and any(o['kind']=='wire' and o['pageId']==page_id and path_key(o['attributes']['points'])==path_key([hotspot,lead_end]) for o in objects):raise CadenceError('net_symbol_conflict','Lead wire already exists.')
    expected=copy.deepcopy(objects)
    expected.append({'kind':kind,'pageId':page_id,'attributes':{'name':name,'sourceSymbol':cache,'location':copy.deepcopy(location),'hotSpot':copy.deepcopy(hotspot),'rotationCode':rotation,'mirrorCode':mirror,'isBus':False}})
    if lead_end is not None:expected.append({'kind':'wire','pageId':page_id,'attributes':{'points':[copy.deepcopy(hotspot),copy.deepcopy(lead_end)],'net':name}})
    return expected

class CaptureNetSymbolCreates(CapturePartEdits):
    kind='capture_net_symbol_create'
    max_record_bytes=65536
    def __init__(self,config,capture,library):super().__init__(config,capture);self.library=library
    def plan(self,sid,page_id,lid,symbol_id,name,location,hotspot,expectations,rotation=0,mirror=0,lead_end=None):
        with self.capture.lock,self.library.lock:
            session=self.capture._session(sid);data=session['data'];page=next((p for p in data['page'] if p['objectId']==page_id),None)
            if page is None:raise CadenceError('object_not_found','Page is outside this session.')
            sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity must be unique.')
            query_net_symbols(self.library,lid,limit=1);lib=self.library._session(lid);symbol=next((s for s in lib['netSymbols'] if s['symbolId']==symbol_id),None)
            if symbol is None:raise CadenceError('object_not_found','Symbol is outside this immutable library session.')
            cache='MCP_NET_'+new_id('s').split('-',1)[1][:16];objects=inventory(self.capture,sid)
            expected_objects=symbol_expectation(objects,page_id,symbol['kind'],name,cache,location,hotspot,rotation,mirror,lead_end)
            expected_data=expected_definitions(data,page_id,expectations);geometry=page_geometry(self.capture,sid,page_id);lead_pin=None
            if lead_end is not None:
                candidates=[]
                for part in (p for p in data['part'] if p['pageId']==page_id):
                    for pin in geometry[part['reference']]['pins']:
                        if pin['hotSpot']==lead_end:candidates.append((part,pin))
                if len(candidates)!=1:raise CadenceError('ambiguous_lead_target','Lead must end at exactly one existing scalar pin hotspot.')
                part,pin=candidates[0];matches=[p for p in data['pin'] if p['partId']==part['objectId'] and (p['number'],p['name'])==(pin['number'],pin['name'])]
                if not pin['number'] or len(matches)!=1 or matches[0]['connected']:raise CadenceError('unsupported_lead_target','Lead creation currently supports an unbound physical pin only.')
                unit=read_units(self.capture,sid)[part['objectId']]
                if unit['kind']!='placed' or unit['packageSize']!=1 or unit['isExternalDesignPart']:raise CadenceError('unsupported_lead_target','Lead target must be an internal single-unit placed pin.')
                lead_pin={'reference':part['reference'],'number':pin['number'],'name':pin['name']}
                requested=next(r for r in expectations if (r['reference'],r['pinNumber'])==(part['reference'],pin['number']))
                if not requested['connected'] or requested['net']!=name:raise CadenceError('invalid_lead_expectation','Explicit target pin must expect the new net name.')
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'sourceLibrary':str(lib['directory']/'library.olb'),'libraryFingerprint':lib['revision'],'symbolId':symbol_id,'symbol':symbol['name'],'symbolType':symbol['nativeTypeCode'],'symbolKind':symbol['kind'],'cacheName':cache,'operation':'create_net_symbol','schematicName':sch['name'],'pageName':page['name'],'name':name,'location':location,'expectedHotSpot':hotspot,'rotation':rotation,'mirror':mirror,'leadEnd':lead_end,'leadPin':lead_pin,'expectedConnections':expectations,'expectedDefinitionDigest':definition_baseline(expected_data),'connectionDigest':connection_digest(data,expected_objects),'expectedGeometry':geometry}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Net symbol plan exceeds durable bounds.')
            self.capture._session(sid);self.library._session(lid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('schematicName','pageName','symbolId','symbol','symbolKind','cacheName','name','location','expectedHotSpot','rotation','mirror','leadEnd','leadPin','expectedConnections','sourceFingerprint','libraryFingerprint')}
    def preflight(self,p):
        if not isinstance(p.get('cacheName'),str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,30}',p['cacheName']):raise CadenceError('invalid_plan','Copied symbol name exceeds the verified native31-character limit.')
        super().preflight(p);source=checked_path(p['sourceLibrary'],(self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower()!='.olb' or sha256(source)!=p['libraryFingerprint']:raise CadenceError('target_changed','Symbol source snapshot changed after planning.')
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);write_json(d/'net-symbol.json',{**{k:p[k] for k in ('schematicName','pageName','symbol','symbolType','cacheName','name','location','rotation','mirror','expectedHotSpot')},'kind':p['symbolKind'],'leadEnabled':p['leadEnd'] is not None,'leadEnd':p['leadEnd'] or []});return super().execute(d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'create_net_symbol.tcl',self.config.install_root,d/'design.dsn',p['sourceLibrary'],d/'net-symbol.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        result=super().verify(d,p,native_completed)
        if p['leadEnd'] is not None:
            target=d/'design.dsn';before=sha256(target)
            if before!=result['artifact']['sha256']:raise CadenceError('target_changed','Output changed between verification stages.')
            out=d/(new_id('symbol-binding')+'.json');run_tcl(self.config,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],d)
            if out.stat().st_size>32*1024*1024:raise CadenceError('output_limit','Binding evidence exceeds limit.')
            rows=json.loads(out.read_text(encoding='utf-8'));rows=[r for r in rows if (r['schematicName'],r['pageName'])==(p['schematicName'],p['pageName'])]
            symbols=[r for r in rows if r['kind']==p['symbolKind'] and r['name']==p['name'] and r['hotSpot']==p['expectedHotSpot']];wires=[r for r in rows if r['kind']=='wire' and path_key(r['points'])==path_key([p['expectedHotSpot'],p['leadEnd']])];pins=[r for r in rows if r['kind']=='pin' and all(r[k]==v for k,v in p['leadPin'].items())]
            if any(len(x)!=1 for x in (symbols,wires,pins)) or symbols[0]['group'] is None or len({x[0]['group'] for x in (symbols,wires,pins)})!=1 or any(x[0]['netName']!=p['name'] for x in (symbols,wires,pins)):raise CadenceError('net_symbol_binding_mismatch','Symbol, lead and target pin do not share the expected nonnull native page net.')
            if sha256(target)!=before:raise CadenceError('target_changed','Binding read changed output.')
        self.preflight(p);result.update(scope='source_bound_page_definition_net_symbol_create',symbolKind=p['symbolKind'],sourceLibraryModified=False,leadBindingVerified=p['leadEnd'] is not None,occurrenceConnectivityVerified=False)
        result['artifact']['artifactId']='net-symbol-'+d.name.removeprefix('plan-');result['notChecked']+=['source_symbol_graphic_equivalence','full_rotation_hotspot_model','cross_page_global_offpage_flat_connectivity','dependency_closure','pspice_ground_zero_semantics']
        return result

