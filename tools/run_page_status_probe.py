from pathlib import Path
import argparse,json
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);repo=Path(__file__).resolve().parents[1];cfg=Config(a.install_root,root,(repo/'.local',),45)
cases={'empty':repo/'.local/save-order-exit-signals-20261024/empty/design.dsn','wire':repo/'.local/save-order-exit-signals-20261024/direct/design.dsn','existing':repo/'.local/wire-alias-0666b70746/output/design.dsn'}
rows=[]
for name,source in cases.items():
    before=sha256(source);out=root/(name+'.json')
    process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,source,out],root,process_env(cfg),45)
    assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
    row={'case':name,'sourceHash':before,'sourceUnchanged':sha256(source)==before,'process':process,'result':json.loads(out.read_text(encoding='utf-8'))};rows.append(row)
    print(json.dumps({'case':name,'result':row['result']},ensure_ascii=True),flush=True)
(root/'report.json').write_text(json.dumps({'scope':'read-only native code/message diagnosis; no status ignored in production','rows':rows},indent=2),encoding='utf-8')
