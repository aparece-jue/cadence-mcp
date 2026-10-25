"""Predeclared lateral connectivity matrix on a new owned design."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60);original=cfg.install_root/'tools/capture/library/capsym.olb';source_hash=sha256(original);library=root/'library.olb';shutil.copyfile(original,library);target=root/'design.dsn'
expected={'schematic':'TOP','pages':['PAGE_A','PAGE_B'],'pairs':[{'y':110,'sameFlatNet':True,'global':False},{'y':210,'sameFlatNet':False,'global':False},{'y':310,'sameFlatNet':True,'global':True},{'y':410,'sameFlatNet':True,'global':False}],'wireCount':8,'flatNetCount':5}
write_json(root/'expected.json',expected);report={'passed':False,'scope':'root schematic lateral wire-network partition; not pin/occurrence hierarchy or public writer','readers':[],'libraryBefore':source_hash}
try:
 report['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_cross_page.tcl'),str(cfg.install_root),str(library),str(target),str(root/'receipt.json')],root,process_env(cfg),60);report['receipt']=json.loads((root/'receipt.json').read_text());assert report['process']['returnCode']==0 and report['receipt']['saved'],'native fixture creation failed';saved=sha256(target);report['savedSha256']=saved
 for mode in ('plain','update'):
  row={'mode':mode,'passed':False};report['readers'].append(row);out=root/(mode+'.json')
  try:
   run_tcl(cfg,'inspect_cross_page.tcl',[str(target),mode,str(out)],root);rows=json.loads(out.read_text());assert len(rows)==8 and len({r['flatGroup'] for r in rows})==5
   for pair in expected['pairs']:
    selected=[next(r for r in rows if r['pageName']==page and r['points']==[[100,pair['y']],[200,pair['y']]]) for page in expected['pages']]
    assert (selected[0]['flatGroup']==selected[1]['flatGroup'])==pair['sameFlatNet'];assert all(r['isGlobal']==pair['global'] for r in selected)
   row['passed']=sha256(target)==saved;row['flatGroups']=len({r['flatGroup'] for r in rows})
  except Exception as e:
   row['error']=str(e)
   if Path(str(out)+'.error.json').exists():row['nativeError']=json.loads(Path(str(out)+'.error.json').read_text())
  report['savedHashUnchanged']=sha256(target)==saved;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(mode,row['passed'],row.get('nativeError',row.get('error')),flush=True)
 # A separate page-native reader must also show each symbol attached to its explicit short wire.
 out=root/'bindings.json';run_tcl(cfg,'inspect_net_symbol_bindings.tcl',[str(target),str(out)],root);bindings=json.loads(out.read_text());symbols=[r for r in bindings if r['kind'] in ('global','offpage')];assert len(symbols)==8
 for symbol in symbols:
  wires=[r for r in bindings if r['kind']=='wire' and r['pageName']==symbol['pageName'] and r['points'][0]==symbol['hotSpot']];assert len(wires)==1 and symbol['group'] is not None and symbol['group']==wires[0]['group']
 report['pageSymbolWireBindingPassed']=True;report['savedHashUnchanged']=sha256(target)==saved;report['passed']=all(r['passed'] for r in report['readers']) and report['savedHashUnchanged']
except Exception as e:report['error']=str(e)
report['libraryAfter']=sha256(original);report['privateLibraryUnchanged']=sha256(library)==source_hash;report['passed'] &= report['libraryAfter']==source_hash and report['privateLibraryUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
