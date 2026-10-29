"""Private native create/delete display probe with independent all-instance snapshots."""
import copy,json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_property_layers import read_property_layers
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_display_fonts import read_fonts
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/display-lifecycle-20261029';root.mkdir(exist_ok=False);source=r/'.local/crosspage-overrides-source-20261029/source.dsn';before=sha256(source);cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,root),60)
def snapshot(path,label):
 cap=CaptureService(cfg);sid=cap.open(cap.create_workspace(str(path))['workspaceId'])['sessionId'];s=cap.sessions[sid];units=read_units(cap,sid)
 try:
  layers={p['objectId']:{k:v for k,v in read_property_layers(cap,sid,p['objectId']).items() if k in ('effective','user','display')} for p in s['data']['part']}
  owner=next(p for p in s['data']['part'] if p['reference']=='U501');page=next(p for p in s['data']['page'] if p['objectId']==owner['pageId']);sch=next(p for p in s['data']['schematic'] if p['objectId']==owner['schematicId'])
  result={'layers':layers,'fonts':read_fonts(cfg,s['design'],s['design'].parent,units),'definition':definition_baseline(s['data']),'owner':owner,'page':page['name'],'schematic':sch['name']};(root/(label+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
 finally:cap.close(sid)
report={'passed':False,'fullE02Accepted':False,'publicLifecycleAvailable':False}
try:
 base=snapshot(source,'before');owner=base['owner'];pid=owner['objectId'];name='PCB Footprint';assert not any(p['name']==name for p in base['layers'][pid]['display'])
 wanted={'name':name,'value':'CUSTOM_00123','location':[-40,60],'rotationCode':1,'displayTypeCode':2,'colorCode':0};(root/'expected.json').write_text(json.dumps(wanted,indent=2)+'\n',encoding='utf-8');oracle=sha256(root/'expected.json');current=source
 template=(ADAPTERS/'edit_display_property.tcl').read_text(encoding='utf-8')
 for mode in ['create','delete']:
  directory=root/mode;directory.mkdir();target=directory/'design.dsn';shutil.copy2(current,target)
  text=template.replace('source [file join [file dirname [info script]] json.tcl]','source {'+(ADAPTERS/'json.tcl').as_posix()+'}')
  if mode=='create':
   a=text.index('                            set display [$part GetDisplayProp');b=text.index('                            set phase marking_page',a)
   block='''                            set state [DboState];set display [$part GetDisplayProp [cmcp::cs $propertyName] $state]
                            if {$display ne "NULL"} {error display_already_exists}
                            if {[$state Failed] && [$state Code]!=1002} {error "unexpected_missing_display_[$state Code]"}
                            set state [DboState];set font [DboTclHelper_sMakeLOGFONT Arial -11 0 0 0 400 0 0 0 0 7 0 1 16]
                            set display [$part NewDisplayProp $state [cmcp::cs $propertyName] [DboTclHelper_sMakeCPoint $newX $newY] $newRotation $font 0];cmcp::check $state
                            cmcp::check [$display SetDisplayType $newType]
                            $display SetBoundingBoxDirty 1
                            $display SetOwnerBoundingBoxDirty 1
''';text=text[:a]+block+text[b:]
  else:
   a=text.index('                            set phase setting_display_property');b=text.index('                            set phase marking_page',a);text=text[:a]+'                            cmcp::check [$part DeleteDisplayProp $display]\n'+text[b:]
  text=text.replace('cmcp::q display_layout','cmcp::q display_'+mode);adapter=directory/'probe.tcl';adapter.write_text(text,encoding='utf-8')
  command=[cfg.install_root/'tcltk/bin/tclsh.exe',adapter,cfg.install_root,target,directory/'receipt.json',pid,'100000',name,'-40','60','1','2','-40','60','1','2',base['schematic'],base['page'],owner['reference']]
  process=run_owned_process(command,directory,process_env(cfg),60);report[mode+'Process']=process;assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
  actual=snapshot(target,mode+'-reopened');assert actual['definition']==base['definition'];expected_layers=copy.deepcopy(base['layers'])
  if mode=='create':expected_layers[pid]['display']=sorted(expected_layers[pid]['display']+[wanted],key=lambda p:p['name'])
  assert actual['layers']==expected_layers
  fonts=copy.deepcopy(actual['fonts'])
  # Remove only the newly declared display font; every original instance/font must remain.
  if mode=='create':
   added=[(row,p) for row in fonts for p in row['fonts'] if p['name']==name and not any(p['name']==old['name'] for b in base['fonts'] if b['nativeId']==row['nativeId'] for old in b['fonts'])];assert len(added)==1
   row,p=added[0];assert p['font']==['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16];row['fonts'].remove(p)
  assert fonts==base['fonts'];current=target
 report.update(passed=True,createSaveReopenAccepted=True,deleteSaveReopenAccepted=True,allInstanceDataAndOtherDisplayFontsPreserved=True,oracleUnchanged=sha256(root/'expected.json')==oracle)
except BaseException:report['error']=traceback.format_exc()
report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
