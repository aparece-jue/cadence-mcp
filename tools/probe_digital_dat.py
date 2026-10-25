from pathlib import Path
import argparse,json,shutil
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-dat'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_dat.resolve(strict=True);before=sha256(source);cfg=Config(a.install_root,root/'work',(source.parent,),45)
copied=root/'copied.dat';shutil.copyfile(source,copied);assert sha256(copied)==before
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_digital_dat.tcl',cfg.install_root,copied,root/'native.json'],root,process_env(cfg),45)
report={'scope':'private fixed digital/mixed metadata representation read','process':process,'sourceUnchanged':sha256(source)==before,'copyUnchanged':sha256(copied)==before,'sourceSha256':before}
if (root/'native.json').exists():report['native']=json.loads((root/'native.json').read_text(encoding='utf-8'))
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
