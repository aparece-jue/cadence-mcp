"""Native fresh-design save ordering with predeclared minimal topology."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45);report={'passed':False,'scope':'minimal fresh DSN save ordering; not full document CRUD','cases':[]}
for mode in ('empty','direct','initial_design','initial_page','save_as','no_page_save'):
 d=root/mode;d.mkdir();expected={'schematic':['ROOT'],'pages':['MAIN'],'parts':0,'pins':0,'wires':[] if mode=='empty' else [[[100,100],[300,100]]]};write_json(d/'expected.json',expected);row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_design_save_order.tcl'),str(cfg.install_root),mode,str(d),str(d/'receipt.json')],d,process_env(cfg),45);row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']['saved'],'native fixture not saved';target=d/('final.dsn' if mode=='save_as' else 'design.dsn');before=sha256(target);row['targetSha256']=before
  row['readers']=[]
  for script,name,extra in [('inspect.tcl','definition',['100000']),('inspect_page_objects.tcl','connections',['connections'])]:
   reader={'script':script,'passed':False};row['readers'].append(reader);out=d/(name+'.json')
   try:
    run_tcl(cfg,script,[str(target),str(out),*extra],d);data=json.loads(out.read_text())
    if name=='definition':assert [s['name'] for s in data['schematic']]==expected['schematic'] and [p['name'] for p in data['page']]==expected['pages'] and not data['part'] and not data['pin']
    else:assert [o['attributes']['points'] for o in data['objects'] if o['kind']=='wire']==expected['wires'] and all(o['kind']=='wire' for o in data['objects'])
    reader['passed']=True
   except Exception as e:reader['error']=str(e)
  row['outputHashUnchanged']=sha256(target)==before;row['passed']=row['outputHashUnchanged'] and all(r['passed'] for r in row['readers'])
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(mode,row['passed'],row.get('error'),row.get('readers'),flush=True)
report['passed']=all(r['passed'] for r in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
