"""Official copied symbol -> owned DSN global/offpage placement discovery."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import connection_digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--align-hotspots',action='store_true')
p.add_argument('--wire-lead',action='store_true')
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.source.parent,),60);olb=cfg.install_root/'tools/capture/library/capsym.olb'
report={'passed':False,'scope':'native source-bound symbol placement discovery','cases':[],'sourceBefore':sha256(a.source),'libraryBefore':sha256(olb)}
def read_source(script,name,extra):
 out=root/(name+'.json');run_tcl(cfg,script,[str(a.source),str(out),*extra],root);return json.loads(out.read_text(encoding='utf-8'))
baseline=read_source('inspect.tcl','before-definition',['100000']);baseline_objects=read_source('inspect_page_objects.tcl','before-connections',['connections'])['objects'];selected_page=next(p['objectId'] for p in baseline['page'] if p['name']=='MCP_PLACE')
origins={'global':[280,300],'offpage':[290,300],'global90':[290,300],'offpage90':[280,310]}
for kind,symbol,name,rotation,mirror in [('global','VCC','MCP_SUPPLY',0,0),('offpage','OFFPAGELEFT-L','MCP_LINK',0,0),('global90','GND','MCP_GROUND',1,1),('offpage90','OFFPAGELEFT-L','MCP_LINK',1,1)]:
 row={'case':kind,'passed':False};report['cases'].append(row);d=root/kind;d.mkdir();target=d/'design.dsn';library=d/'capsym.olb';shutil.copyfile(a.source,target);shutil.copyfile(olb,library)
 spec={'kind':'global' if kind.startswith('global') else 'offpage','symbol':symbol,'name':name,'location':origins[kind] if a.align_hotspots else [290,310],'rotation':rotation,'mirror':mirror};write_json(d/'request.json',spec)
 if a.wire_lead:
  spec['location']=[spec['location'][0]-50,spec['location'][1]];spec['wireLead']=True
  (d/'request.json').unlink();write_json(d/'request.json',spec)
 import copy
 expected=copy.deepcopy(baseline)
 if a.align_hotspots:
  for pin in expected['pin']:
   if pin['reference']=='R101' and pin['number']=='1':pin.update(connected=True,net=name)
 wanted_objects=copy.deepcopy(baseline_objects);wanted_objects.append({'kind':spec['kind'],'pageId':selected_page,'attributes':{'name':name,'sourceSymbol':'MCP_NETSYM','location':spec['location'],'hotSpot':[290,310] if a.align_hotspots else {'global':[300,320],'offpage':[290,320],'global90':[290,320],'offpage90':[300,310]}[kind],'rotationCode':rotation,'mirrorCode':mirror,'isBus':False}})
 if a.wire_lead:
  wanted_objects[-1]['attributes']['hotSpot']=[240,310]
  wanted_objects.append({'kind':'wire','pageId':selected_page,'attributes':{'points':[[240,310],[290,310]],'net':name}})
 write_json(d/'expected.json',{'definitionDigest':definition_baseline(expected),'connectionDigest':connection_digest(expected,wanted_objects),'symbol':wanted_objects[-1]})
 try:
  row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_net_symbol_add.tcl'),str(cfg.install_root),str(target),str(library),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60)
  if (d/'receipt.json').exists():row['receipt']=json.loads((d/'receipt.json').read_text())
  for script,name,extra in [('inspect.tcl','definition',['100000']),('inspect_page_objects.tcl','connections',['connections'])]:run_tcl(cfg,script,[str(target),str(d/(name+'.json')),*extra],d)
  data=json.loads((d/'definition.json').read_text());objects=json.loads((d/'connections.json').read_text())['objects'];row['pins']=[p for p in data['pin'] if p['reference']=='R101'];row['symbolObjects']=[o for o in objects if o['kind']==spec['kind']];row['definitionMatchesDeclared']=definition_baseline(data)==definition_baseline(expected);row['connectionObjectsMatchDeclared']=connection_digest(data,objects)==connection_digest(expected,wanted_objects);row['passed']=row['process']['returnCode']==0 and row['definitionMatchesDeclared'] and row['connectionObjectsMatchDeclared'];row['libraryCopyUnchanged']=sha256(library)==report['libraryBefore'];row['passed'] &= row['libraryCopyUnchanged']
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(kind,row['passed'],row.get('error'),row.get('receipt'),flush=True)
report.update(sourceAfter=sha256(a.source),libraryAfter=sha256(olb));report['passed']=all(c['passed'] for c in report['cases']) and report['sourceBefore']==report['sourceAfter'] and report['libraryBefore']==report['libraryAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
