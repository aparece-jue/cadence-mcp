import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);src=a.source.resolve(strict=True);before=sha256(src);cfg=Config(a.install_root,root,(src.parent,),45);report={'sourceBefore':before,'scope':'native netlist mode/log diagnostic only','cases':[]}
for mode in ('minimal','legacy'):
 d=root/mode;d.mkdir();dsn=d/'design.dsn';shutil.copyfile(src,dsn);out=d/'receipt.json';target=d/'generated.net';row={'mode':mode};report['cases'].append(row)
 row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'generate_pspice_netlist_diagnostic.tcl'),str(cfg.install_root),str(dsn),str(target),mode,str(out)],d,process_env(cfg),45)
 if out.exists():row['receipt']=json.loads(out.read_text())
 row.update(privateSourceUnchanged=sha256(dsn)==before,targetExists=target.is_file(),targetSize=target.stat().st_size if target.is_file() else None);report['sourceAfter']=sha256(src);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
