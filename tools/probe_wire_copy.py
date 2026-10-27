import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,CadenceError
from cadence_mcp.environment import process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process

p=argparse.ArgumentParser(description='Official DboPage StartTransaction comparison, fixed new-wire oracle and independent reopen; not a public operation.')
for name in ('install-root','workspace-root','source'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),30)
oracle={'schematics':['ROOT'],'pages':['MAIN'],'wirePoints':[[100,100],[300,100]],'parts':0,'pins':0}
(root/'expected.json').write_text(json.dumps(oracle,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json');report={'anyPassed':False,'cases':[],'expectedSha256':expected_hash}
source=a.source.resolve(strict=True);source_hash=sha256(source)
for mode in ('direct_loaded','copy0','copy1'):
 directory=root/mode;directory.mkdir();row={'mode':mode,'passed':False};report['cases'].append(row)
 row['process']=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_suffix('.tcl'),cfg.install_root,directory,mode,directory/'receipt.json',source],directory,process_env(cfg),30)
 if (directory/'receipt.json').exists():row['receipt']=json.loads((directory/'receipt.json').read_text())
 try:
  assert row['process']['state']=='exited' and row['process']['returnCode']==0 and row.get('receipt',{}).get('saved')
  target=directory/'design.dsn';row['designSha256']=sha256(target)
  run_tcl(cfg,'inspect.tcl',[str(target),str(directory/'definitions.json'),'100000'],directory)
  data=json.loads((directory/'definitions.json').read_text());assert [x['name'] for x in data['schematic']]==oracle['schematics'] and [x['name'] for x in data['page']]==oracle['pages'] and not data['part'] and not data['pin']
  run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(directory/'objects.json'),'connections'],directory)
  objects=json.loads((directory/'objects.json').read_text())['objects'];assert len(objects)==1 and objects[0]['kind']=='wire' and objects[0]['attributes']['points']==oracle['wirePoints']
  row['passed']=True
 except Exception as error:row.update(error=str(error),errorCode=getattr(error,'code',None))
 print(json.dumps({'mode':mode,'saved':row.get('receipt',{}).get('saved'),'passed':row['passed'],'error':row.get('error')}),flush=True)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
report['sourceUnchanged']=sha256(source)==source_hash;assert report['sourceUnchanged']
report['expectedUnchanged']=sha256(root/'expected.json')==expected_hash;report['anyPassed']=any(x['passed'] for x in report['cases']) and report['expectedUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
