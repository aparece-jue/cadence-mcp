import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','transaction-root','copy-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.transaction_root.resolve(),a.copy_root.resolve()),30)
sources=[(prefix+'-'+mode,base/mode/'design.dsn') for prefix,base,modes in [('transaction',a.transaction_root.resolve(),('baseline','transaction','undo_transaction')),('copy',a.copy_root.resolve(),('direct_loaded','copy0','copy1'))] for mode in modes]
report={'anyPassed':False,'scope':'Read-only correction of the prior probe entry-point error; no native write replay','rows':[]}
for label,source in sources:
 row={'case':label,'passed':False,'sourceHash':sha256(source)};report['rows'].append(row);output=root/(label+'-status.json')
 process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,source,output],root,process_env(cfg),30)
 row['statusProcess']=process
 if output.exists():row['status']=json.loads(output.read_text(encoding='utf-8'))
 try:
  definitions=root/(label+'-definitions.json');run_tcl(cfg,'inspect.tcl',[str(source),str(definitions),'100000'],root)
  data=json.loads(definitions.read_text(encoding='utf-8'));assert [x['name'] for x in data['schematic']]==['ROOT'] and [x['name'] for x in data['page']]==['MAIN'] and not data['part'] and not data['pin']
  output=root/(label+'-objects.json');run_tcl(cfg,'inspect_page_objects.tcl',[str(source),str(output),'connections'],root)
  objects=json.loads(output.read_text(encoding='utf-8'))['objects'];assert len(objects)==1 and objects[0]['kind']=='wire' and objects[0]['attributes']['points']==[[100,100],[300,100]]
  row['passed']=True
 except Exception as error:row.update(error=str(error),errorCode=getattr(error,'code',None))
 row['sourceUnchanged']=sha256(source)==row['sourceHash'];assert row['sourceUnchanged']
 print(json.dumps({'case':label,'passed':row['passed'],'status':row.get('status')}),flush=True)
report['anyPassed']=any(x['passed'] for x in report['rows']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
