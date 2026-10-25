"""Durable single-unit unbound scalar NC marker edits on isolated copies."""
import copy,json
from .capture_edit import definition_baseline
from .capture_part_edit import CapturePartEdits,page_geometry
from .capture_references import read_units
from .capture_wire import inventory,connection_digest
from .core import CadenceError,write_json
from .environment import ADAPTERS

def nc_expectation(data,objects,pin,hotspot,enabled):
    matches=[o for o in objects if o['kind']=='nc' and o['attributes']['partId']==pin['partId'] and o['attributes']['number']==pin['number']]
    if len(matches)>1:raise CadenceError('ambiguous_nc','Multiple NC markers match one scalar pin.')
    if bool(matches)==enabled:raise CadenceError('no_change','NC flag already matches the requested state.')
    result=copy.deepcopy(objects)
    if matches:result.remove(matches[0])
    else:result.append({'kind':'nc','pageId':pin['pageId'],'attributes':{'partId':pin['partId'],'pinId':pin['objectId'],'reference':pin['reference'],'number':pin['number'],'hotSpot':hotspot}})
    return bool(matches),connection_digest(data,result)

class CaptureNcEdits(CapturePartEdits):
    kind='capture_nc'
    max_record_bytes=65536
    def plan(self,sid,pin_id,enabled):
        if type(enabled) is not bool:raise CadenceError('invalid_nc','enabled must be a strict boolean.')
        with self.capture.lock:
            session=self.capture._session(sid);data=session['data'];pin=next((p for p in data['pin'] if p['objectId']==pin_id),None)
            if pin is None:raise CadenceError('object_not_found','Pin is outside the immutable definition session.')
            if pin['connected']:raise CadenceError('connected_pin_refused','This NC operation supports unbound scalar pins only.')
            if not pin['number'] or sum(p['partId']==pin['partId'] and p['number']==pin['number'] for p in data['pin'])!=1:raise CadenceError('ambiguous_pin','A distinct scalar physical pin number is required.')
            unit=read_units(self.capture,sid)[pin['partId']]
            if unit['kind']!='placed' or unit['packageSize']!=1 or unit['isExternalDesignPart']:raise CadenceError('unsupported_nc_scope','NC currently supports internal single-unit placed parts.')
            page=next(p for p in data['page'] if p['objectId']==pin['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==pin['schematicId'])
            if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Qualified page identity must be unique.')
            geometry=page_geometry(self.capture,sid,page['objectId']);row=geometry[pin['reference']]
            targets=[p for p in row['pins'] if (p['number'],p['name'])==(pin['number'],pin['name'])]
            if len(targets)!=1:raise CadenceError('ambiguous_pin','Native hotspot identity does not uniquely match the selected pin.')
            hotspot=targets[0]['hotSpot'];old,expected=nc_expectation(data,inventory(self.capture,sid),pin,hotspot,enabled)
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],'operation':'set_nc','pinId':pin_id,'partId':pin['partId'],'nativePartId':unit['nativeId'],'schematicName':sch['name'],'pageName':page['name'],'reference':pin['reference'],'pinNumber':pin['number'],'pinName':pin['name'],'hotSpot':hotspot,'oldFlag':int(old),'newFlag':int(enabled),'expectedGeometry':geometry,'expectedDefinitionDigest':definition_baseline(data),'connectionDigest':expected}
            if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','NC plan exceeds durable bounds.')
            self.capture._session(sid);return self.create_plan(payload)
    def preview(self,p):return {k:p[k] for k in ('pinId','partId','schematicName','pageName','reference','pinNumber','pinName','hotSpot','oldFlag','newFlag','sourceFingerprint')}
    def execute(self,d,p,cancel,on_started):
        self.preflight(p);write_json(d/'nc-edit.json',{k:p[k] for k in ('nativePartId','schematicName','pageName','reference','pinNumber','pinName','hotSpot','oldFlag','newFlag')});return super().execute(d,p,cancel,on_started)
    def native_command(self,d,p):return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_nc.tcl',self.config.install_root,d/'design.dsn',d/'nc-edit.json',d/'native-result.json']
    def verify(self,d,p,native_completed):
        value=super().verify(d,p,native_completed);value.update(scope='single_unit_unbound_scalar_pin',expectedNC=bool(p['newFlag']),scalarPinNCVerified=True)
        value['artifact']['artifactId']='nc-'+d.name.removeprefix('plan-');value['notChecked'].remove('attached_nc_lifecycle');value['notChecked']+=['bus_pin_nc','connected_pin_nc_cleanup','external_design_closure']
        return value

