"""COM apartment initialization differential on isolated embedded Tcl workers."""
import argparse,json,shutil,sys
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);src=a.source.resolve(strict=True);before=sha256(src);cfg=Config(a.install_root,root,(src.parent,),45);report={'sourceBefore':before,'hypothesis':'COM apartment required by PSpice explorer; unproven until differential observed','cases':[]}
for mode in ('none','sta','mta'):
 d=root/mode;d.mkdir();dsn=d/'design.dsn';shutil.copyfile(src,dsn);target=d/'generated.net';receipt=d/'receipt.json';row={'com':mode};report['cases'].append(row)
 row['process']=run_owned_process([sys.executable,str(Path(__file__).with_name('embedded_tcl_com_probe.py')),'--install-root',str(cfg.install_root),'--script',str(ADAPTERS/'generate_pspice_netlist_diagnostic.tcl'),'--source',str(dsn),'--target',str(target),'--receipt',str(receipt),'--com',mode],d,process_env(cfg),45)
 if receipt.exists():row['receipt']=json.loads(receipt.read_text())
 row.update(targetSize=target.stat().st_size if target.exists() else None,privateSourceUnchanged=sha256(dsn)==before);report['sourceAfter']=sha256(src);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
