"""One copied package, one base reference, multiple explicit device/view instances."""
import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.capture_part_edit import page_geometry,geometry_row
from cadence_mcp.capture_geometry import read_part_geometry
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','library-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--cases',nargs='+',choices=('shared_dual','heterogeneous_power'),default=['shared_dual','heterogeneous_power']);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);cfg=Config(a.install_root,root,(root,),60);source_hash=sha256(source);report={'passed':False,'sourceBefore':source_hash,'scope':'same base reference/cache multiunit page definitions and explicit power wires; not occurrence/physical board packaging certification','cases':[]}
def read(script,path,d,name,extra=[]):
 out=d/(name+'.json');run_tcl(cfg,script,[str(path),str(out),*extra],d);return json.loads(out.read_text())
before=read('inspect.tcl',source,root,'baseline',['100000']);objects=read('inspect_page_objects.tcl',source,root,'baseline-objects',['connections'])['objects'];page_id=next(p['objectId'] for p in before['page'] if p['name']=='MCP_PLACE');schematic_id=next(p['schematicId'] for p in before['page'] if p['objectId']==page_id)
for case in a.cases:
 libspec=json.loads((a.library_root/case/'spec.json').read_text());libsource=(a.library_root/case/'library.olb').resolve(strict=True);lib_hash=sha256(libsource)
 for wired in (False,True):
  name=case+('-power-wire' if wired else '-unbound');d=root/name;d.mkdir();target=d/'design.dsn';library=d/'library.olb';shutil.copyfile(source,target);shutil.copyfile(libsource,library);units=[];declared=[];wanted=copy.deepcopy(before);wanted_objects=copy.deepcopy(objects);hotspots=[]
  for i,dev in enumerate(libspec['devices']):
   variant='Convert' if dev['designator']=='B' else 'Normal';sym=next(s for s in libspec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));location=[1000+200*i,700];units.append({'designator':dev['designator'],'variant':variant,'location':location,'sourcePartName':sym['partName']});pid='new-'+dev['designator'];wanted['part'].append({'objectId':pid,'pageId':page_id,'schematicId':schematic_id,'reference':'U501'});mapping={p['position']:p for p in dev['mapping']};pins=[]
   for pin in sym['pins']:
    number=mapping[pin['position']]['number'];hot=[location[j]+pin['hotSpot'][j] for j in (0,1)];connected=wired and pin['name']=='VCC';wanted['pin'].append({'objectId':pid+'/'+number,'partId':pid,'pageId':page_id,'schematicId':schematic_id,'reference':'U501','number':number,'name':pin['name'],'connected':connected,'net':'VCC' if connected else ''});pins.append({'number':number,'name':pin['name'],'hotSpot':hot})
    if pin['name']=='VCC':hotspots.append(hot)
   declared.append({'designator':dev['designator'],'reference':'U501','referenceDesignator':'U501'+dev['designator'],'packageSize':len(libspec['devices']),'location':location,'pins':pins})
  paths=[]
  if wired:
   paths=[[hot,[hot[0],650]] for hot in hotspots]+[[[a[0],650],[b[0],650]] for a,b in zip(hotspots,hotspots[1:])]
   for path in paths:wanted_objects.append({'kind':'wire','pageId':page_id,'attributes':{'points':path,'net':'VCC'}})
   wanted_objects.append({'kind':'alias','pageId':page_id,'attributes':{'name':'VCC','location':paths[0][0],'wireId':'declared-power-wire'}})
  request={'packageName':libspec['packageName'],'cacheName':'MCP_GROUP','reference':'U501','schematicName':'HALFADD','pageName':'MCP_PLACE','units':units,'wires':paths};write_json(d/'request.json',request);expected={'definitionDigest':definition_baseline(wanted),'connectionDigest':connection_digest(wanted,wanted_objects),'units':declared};write_json(d/'expected.json',expected);row={'case':name,'passed':False,'libraryBefore':lib_hash};report['cases'].append(row)
  try:
   row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_multiunit_group.tcl'),str(cfg.install_root),str(target),str(library),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60);row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']['saved'],'native group placement failed';saved=sha256(target);data=read('inspect.tcl',target,d,'after',['100000']);obs=read('inspect_page_objects.tcl',target,d,'objects',['connections'])['objects'];identity=read('inspect_reference_units.tcl',target,d,'units');selected=[u for u in identity if u['reference']=='U501'];row['definitionMatches']=definition_baseline(data)==expected['definitionDigest'];row['connectionObjectsMatch']=connection_digest(data,obs)==expected['connectionDigest'];row['identityMatches']=len(selected)==len(declared) and all(any(u['deviceDesignator']==e['designator'] and u['referenceDesignator']==e['referenceDesignator'] and u['packageName']=='MCP_GROUP' and u['packageSize']==e['packageSize'] for u in selected) for e in declared)
   cap=CaptureService(cfg);cap.workspaces['group']={'directory':d,'manifest':{'copiedFingerprint':saved}};sid=cap.open('group')['sessionId']
   try:
    checks=[]
    for u in selected:
     actual=read_part_geometry(cap,sid,u['partId']);exp=next(e for e in declared if e['designator']==u['deviceDesignator']);checks.append(geometry_row(actual)=={'location':exp['location'],'rotationCode':0,'mirrorCode':0,'pins':sorted(exp['pins'],key=lambda p:(p['number'],p['name']))})
    row['unitGeometryMatches']=all(checks) and len(checks)==len(declared)
   finally:cap.close(sid)
   if wired:
    bindings=read('inspect_net_symbol_bindings.tcl',target,d,'bindings');pins=[p for p in bindings if p['kind']=='pin' and p['reference'] in [e['referenceDesignator'] for e in declared] and p['name']=='VCC'];wires=[w for w in bindings if w['kind']=='wire' and w['pageName']=='MCP_PLACE' and w['points'] in paths];row['nativePowerGroupMatches']=len(pins)==len(declared) and len(wires)==len(paths) and pins[0]['group'] is not None and len({p['group'] for p in pins+wires})==1
   row['outputHashUnchanged']=sha256(target)==saved;row['savedSha256']=saved;row['passed']=all(row[k] for k in ('definitionMatches','connectionObjectsMatch','identityMatches','unitGeometryMatches','outputHashUnchanged')) and (not wired or row['nativePowerGroupMatches'])
  except Exception as e:row['error']=str(e)
  row['sourceLibraryUnchanged']=sha256(libsource)==lib_hash and sha256(library)==lib_hash;row['passed'] &= row['sourceLibraryUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,row['passed'],row.get('error'),row.get('receipt'),flush=True)
report['sourceAfter']=sha256(source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceBefore']==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)

