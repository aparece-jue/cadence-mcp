"""Configured native netlist capability inventory, never exports or executes a design."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),30);report={'scope':'native load/command visibility only; no design or netlist acceptance','cases':[]}
for kind in ('pspice','tclnetlist'):
 d=root/kind;d.mkdir();out=d/'runtime.json';row={'kind':kind};report['cases'].append(row)
 row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'inspect_pspice_netlist_runtime.tcl'),str(cfg.install_root),kind,str(out)],d,process_env(cfg),30)
 if out.exists():row['runtime']=json.loads(out.read_text())
 if Path(str(out)+'.error.json').exists():row['nativeError']=json.loads(Path(str(out)+'.error.json').read_text())
 print(json.dumps({'kind':kind,'process':row['process'],'loaded':row.get('runtime',{}).get('loadSucceeded'),'newCommandCount':len(row.get('runtime',{}).get('newCommands',[]))}),flush=True);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

