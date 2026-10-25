import argparse,json
from pathlib import Path
from cadence_mcp.core import Config
from cadence_mcp.environment import run_tcl
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60);run_tcl(cfg,'probe_vector_registration.tcl',[str(root/'report.json')],root);print((root/'report.json').read_text(encoding='utf-8'))
