"""Official typed PortSymbol initialization alternative; no general write certification."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60);src=cfg.install_root/'tools/capture/library/capsym.olb';before=sha256(src);lib=root/'library.olb';shutil.copyfile(src,lib);target=root/'design.dsn';report={'passed':False,'scope':'copied official PortSymbol fresh graph discovery; not public lifecycle or full H03','libraryBefore':before,'readers':[]}
expected={'childPorts':{'IN':[100,110],'OUT':[300,110]},'sourceSymbol':'PORTLEFT-L','sourceType':34,'parentBlock':'BLOCK_A','childSchematic':'CHILD','parentPinCount':2,'childWire':[[100,110],[300,110]],'fullHierarchyConnectivityAccepted':False};write_json(root/'expected.json',expected)
try:
 report['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_hierarchy_ports_copied.tcl'),str(cfg.install_root),str(lib),str(target),str(root/'receipt.json')],root,process_env(cfg),60)
 if (root/'receipt.json').exists():report['receipt']=json.loads((root/'receipt.json').read_text())
 assert target.exists(),'No saved design';saved=sha256(target);report['savedSha256']=saved
 for script,name,extra in [('inspect.tcl','definition',['100000']),('inspect_hierarchy.tcl','tree',[]),('inspect_page_objects.tcl','objects',['connections']),('inspect_net_symbol_bindings.tcl','bindings',[])]:
  row={'script':script,'passed':False};report['readers'].append(row);out=root/(name+'.json')
  try:run_tcl(cfg,script,[str(target),str(out),*extra],root);row['passed']=True
  except Exception as e:
   row['error']=str(e)
   if Path(str(out)+'.error.json').exists():row['nativeError']=json.loads(Path(str(out)+'.error.json').read_text())
  print(name,row['passed'],row.get('nativeError',row.get('error')),flush=True)
 if (root/'objects.json').exists():
  objects=json.loads((root/'objects.json').read_text())['objects'];ports=[o for o in objects if o['kind']=='port'];report['declaredPortHotspotsMatch']=len(ports)==2 and {o['attributes']['name']:o['attributes']['hotSpot'] for o in ports}==expected['childPorts']
 if (root/'bindings.json').exists():
  bindings=json.loads((root/'bindings.json').read_text());ports=[b for b in bindings if b['kind']=='port'];wires=[b for b in bindings if b['kind']=='wire' and b['pageName']=='CHILD_PAGE'];report['childNativeWireBindingMatches']=len(ports)==2 and len(wires)==1 and wires[0]['group'] is not None and all(b['group']==wires[0]['group'] for b in ports)
 report['savedHashUnchanged']=sha256(target)==saved;report['passed']=report['process']['returnCode']==0 and all(r['passed'] for r in report['readers']) and report.get('declaredPortHotspotsMatch',False) and report.get('childNativeWireBindingMatches',False) and report['savedHashUnchanged']
except Exception as e:report['error']=str(e)
report['libraryAfter']=sha256(src);report['privateLibraryUnchanged']=sha256(lib)==before;report['passed'] &= before==report['libraryAfter'] and report['privateLibraryUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
