"""Explicit disjoint VCC/GND oracle plus deliberate short/open native fixtures."""
import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.capture_part_edit import geometry_row
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source','library-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);library_root=a.library_root.resolve(strict=True);cfg=Config(a.install_root,root,(root,),60)
source_hash=sha256(source);lib=library_root/'library.olb';lib_hash=sha256(lib);spec=json.loads((library_root/'spec.json').read_text())
report={'passed':False,'scope':'page-definition explicit VCC/GND separation and planted faults; not flat/occurrence or DRC','cases':[],'sourceBefore':source_hash,'libraryBefore':lib_hash}
def read(script,path,d,name,extra=()):
 out=d/(name+'.json');run_tcl(cfg,script,[str(path),str(out),*extra],d);return json.loads(out.read_text())
baseline=read('inspect.tcl',source,root,'baseline',['100000']);objects=read('inspect_page_objects.tcl',source,root,'baseline-objects',['connections'])['objects'];page=next(p for p in baseline['page'] if p['name']=='MCP_PLACE');pid=page['objectId'];sid=page['schematicId']
old_geometry={part['reference']:geometry_row(read('inspect_part_geometry.tcl',source,root,'old-'+part['reference'],[part['objectId'],'100000','10000'])) for part in baseline['part'] if part['pageId']==pid}
units=[];wanted=copy.deepcopy(baseline);wanted_objects=copy.deepcopy(objects);netpoints={'VCC':[],'GND':[]};expected_units=[]
for i,dev in enumerate(spec['devices']):
 variant='Convert' if dev['designator']=='B' else 'Normal';sym=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));loc=[1000+200*i,700];units.append({'designator':dev['designator'],'variant':variant,'location':loc,'sourcePartName':sym['partName']});part_id='new-'+dev['designator'];wanted['part'].append({'objectId':part_id,'pageId':pid,'schematicId':sid,'reference':'U501'});mapping={m['position']:m['number'] for m in dev['mapping']};pins=[]
 for pin in sym['pins']:
  number=mapping[pin['position']];hot=[loc[j]+pin['hotSpot'][j] for j in (0,1)];name=pin['name'];net=name if name in netpoints else '';wanted['pin'].append({'objectId':part_id+'/'+number,'partId':part_id,'pageId':pid,'schematicId':sid,'reference':'U501','number':number,'name':name,'connected':bool(net),'net':net});pins.append({'number':number,'name':name,'hotSpot':hot})
  if net:netpoints[net].append(hot)
 expected_units.append({'designator':dev['designator'],'referenceDesignator':'U501'+dev['designator'],'location':loc,'pins':pins})
paths=[];labels={};netpaths={}
for net,y in [('VCC',650),('GND',800)]:
 points=netpoints[net];assert points
 wires=[[pt,[pt[0],y]] for pt in points]+[[[left[0],y],[right[0],y]] for left,right in zip(points,points[1:])];netpaths[net]=wires;labels[str(len(paths)+1)]=net;paths.extend(wires)
 for wire in wires:wanted_objects.append({'kind':'wire','pageId':pid,'attributes':{'points':wire,'net':net}})
 wanted_objects.append({'kind':'alias','pageId':pid,'attributes':{'name':net,'location':wires[0][0],'wireId':'declared-'+net}})
expected={'definitionDigest':definition_baseline(wanted),'connectionDigest':connection_digest(wanted,wanted_objects),'units':expected_units,'netPaths':netpaths,'originalPageGeometry':old_geometry}
write_json(root/'expected.json',expected);oracle_hash=sha256(root/'expected.json')
for mode in ('separate','short','open'):
 d=root/mode;d.mkdir();target=d/'design.dsn';shutil.copyfile(source,target);shutil.copyfile(lib,d/'library.olb');actual_paths=copy.deepcopy(paths);actual_labels=dict(labels)
 if mode=='short':actual_paths.append([[1400,650],[1400,720]])
 if mode=='open':actual_paths[0][0]=[1000,660]
 request={'packageName':spec['packageName'],'cacheName':'MCP_GROUP','reference':'U501','schematicName':'HALFADD','pageName':'MCP_PLACE','units':units,'wires':actual_paths,'wireAliases':actual_labels};write_json(d/'request.json',request);row={'case':mode,'passed':False};report['cases'].append(row)
 try:
  row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_multiunit_group.tcl'),str(cfg.install_root),str(target),str(d/'library.olb'),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60);row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']['saved'];saved=sha256(target)
  data=read('inspect.tcl',target,d,'definition',['100000']);obs=read('inspect_page_objects.tcl',target,d,'objects',['connections'])['objects'];identity=read('inspect_reference_units.tcl',target,d,'units');bindings=read('inspect_net_symbol_bindings.tcl',target,d,'bindings');selected=[u for u in identity if u['reference']=='U501'];row['definitionMatches']=definition_baseline(data)==expected['definitionDigest'];row['connectionObjectsMatch']=connection_digest(data,obs)==expected['connectionDigest'];row['unitIdentityMatches']=len(selected)==3 and all(any(u['deviceDesignator']==e['designator'] and u['referenceDesignator']==e['referenceDesignator'] and u['packageName']=='MCP_GROUP' and u['packageSize']==3 for u in selected) for e in expected_units)
  row['unitGeometryMatches']=all(geometry_row(read('inspect_part_geometry.tcl',target,d,'geometry-'+u['deviceDesignator'],[u['partId'],'100000','10000']))=={'location':e['location'],'rotationCode':0,'mirrorCode':0,'pins':sorted(e['pins'],key=lambda p:(p['number'],p['name']))} for u in selected for e in expected_units if u['deviceDesignator']==e['designator']) and len(selected)==3
  current_old={part['reference']:geometry_row(read('inspect_part_geometry.tcl',target,d,'old-'+part['reference'],[part['objectId'],'100000','10000'])) for part in data['part'] if part['pageId']==pid and part['reference']!='U501'};row['originalPageGeometryPreserved']=current_old==old_geometry
  groups={};checks=[]
  for net in netpoints:
   pins=[b for b in bindings if b['kind']=='pin' and b['pageName']=='MCP_PLACE' and b['reference'] in ('U501A','U501B','U501P') and b['name']==net];wires=[b for b in bindings if b['kind']=='wire' and b['pageName']=='MCP_PLACE' and b['points'] in netpaths[net]];members=pins+wires;values={b['group'] for b in members};checks.append(len(pins)==len(netpoints[net]) and len(wires)==len(netpaths[net]) and len(values)==1 and None not in values and all(b['netName']==net for b in members));groups[net]=pins[0]['group'] if pins else None
  row['nativePowerNetworksMatch']=all(checks) and None not in groups.values() and groups['VCC']!=groups['GND'];row['nativeGroups']=groups;row['sourceAndOutputHashesPreserved']=sha256(source)==source_hash and sha256(lib)==lib_hash and sha256(target)==saved and sha256(d/'library.olb')==lib_hash;row['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;row['outputSha256']=saved
  accepted=all(row[k] for k in ('definitionMatches','connectionObjectsMatch','unitIdentityMatches','unitGeometryMatches','originalPageGeometryPreserved','nativePowerNetworksMatch','sourceAndOutputHashesPreserved','oracleUnchanged')) and row['process']['remainingOwnedProcesses']==0;row['electricalAcceptance']=accepted
  # Fault evidence must reject electrical/definition oracle, not merely geometry counts.
  row['passed']=accepted if mode=='separate' else not row['definitionMatches'] and not row['nativePowerNetworksMatch'] and row['unitIdentityMatches'] and row['unitGeometryMatches'] and row['sourceAndOutputHashesPreserved'] and row['oracleUnchanged']
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(mode,row,flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
