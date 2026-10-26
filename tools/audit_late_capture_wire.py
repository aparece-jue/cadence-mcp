"""Verify an already dispatched Capture-host wire result without replay or old-report edits."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','host-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);host=a.host_root.resolve();cfg=Config(a.install_root,root,(host,),60);paths=['report.json','expected.json','receipt.json','boot.txt','design.dsn'];before={n:sha256(host/n) for n in paths};expected=json.loads((host/'expected.json').read_text(encoding='utf-8'));receipt=json.loads((host/'receipt.json').read_text(encoding='utf-8'));assert receipt['saved'] and int((host/'boot.txt').read_text().strip())==20696
report={'passed':False,'scope':'late completion of original dispatch; no mutation replay','originalSha256':before,'bootPid':20696,'receipt':receipt}
try:
 run_tcl(cfg,'inspect.tcl',[str(host/'design.dsn'),str(root/'definitions.json'),'100000'],root);data=json.loads((root/'definitions.json').read_text(encoding='utf-8'));assert [s['name'] for s in data['schematic']]==expected['schematics'] and [p['name'] for p in data['page']]==expected['pages'] and not data['part'] and not data['pin']
 run_tcl(cfg,'inspect_page_objects.tcl',[str(host/'design.dsn'),str(root/'objects.json'),'connections'],root);rows=json.loads((root/'objects.json').read_text(encoding='utf-8'))['objects'];assert [o['attributes']['points'] for o in rows if o['kind']=='wire']==expected['wires'] and all(o['kind']=='wire' for o in rows);report['passed']=True
except Exception as e:report['error']=str(e)
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,host/'design.dsn',root/'page-status.json'],root,process_env(cfg),60);assert process['returnCode']==0 and process['remainingOwnedProcesses']==0;report['nativePageStatus']=json.loads((root/'page-status.json').read_text(encoding='utf-8'))['rows'][-1];report['originalUnchanged']=all(sha256(host/n)==v for n,v in before.items());report['passed']=report['passed'] and report['originalUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'pageStatus':report['nativePageStatus'],'error':report.get('error')}),flush=True)
