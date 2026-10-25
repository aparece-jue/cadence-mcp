import argparse,json
from pathlib import Path
from cadence_mcp.core import Config
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),30);report={'scope':'fixed100-argument signature refusals; no design/session or netlist call accepted','cases':[]}
for kind in ('pspice','tclnetlist'):
 d=root/kind;d.mkdir();out=d/'signatures.json';row={'kind':kind,'process':run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'inspect_netlist_signatures.tcl'),str(cfg.install_root),kind,str(out)],d,process_env(cfg),30)}
 if out.exists():row['signatures']=json.loads(out.read_text())
 report['cases'].append(row);print(json.dumps(row),flush=True)
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
