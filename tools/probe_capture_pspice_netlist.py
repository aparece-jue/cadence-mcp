"""Actual native DSN->PSpice NET discovery, not a simulated or historical output."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);src=a.source.resolve(strict=True);before=sha256(src);cfg=Config(a.install_root,root,(src.parent,),45);report={'scope':'native DSN->NET generation discovery; no profile/CIR/model closure/solver/numeric acceptance','sourceBefore':before,'cases':[]}
for mode in ('missing_design','official_private_copy'):
 d=root/mode;d.mkdir();dsn=d/'design.dsn';target=d/'generated.net';receipt=d/'receipt.json'
 if mode=='official_private_copy':shutil.copyfile(src,dsn)
 row={'mode':mode,'targetAbsentBefore':not target.exists()};report['cases'].append(row)
 row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'generate_pspice_netlist_probe.tcl'),str(cfg.install_root),str(dsn),str(target),str(receipt)],d,process_env(cfg),45)
 if receipt.exists():row['receipt']=json.loads(receipt.read_text())
 row['targetExists']=target.is_file();row['files']=[{'name':f.relative_to(d).as_posix(),'size':f.stat().st_size,'sha256':sha256(f)} for f in d.rglob('*') if f.is_file()]
 if mode=='official_private_copy':row['privateSourceUnchanged']=sha256(dsn)==before
 report['sourceAfter']=sha256(src);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'mode':mode,'process':row['process'],'receipt':row.get('receipt'),'targetExists':row['targetExists']}),flush=True)
