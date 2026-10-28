import json
from pathlib import Path
from cadence_mcp.core import Config
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/annotation-scope-runtime-20261028';root.mkdir(exist_ok=False)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45)
run_tcl(cfg,str(r/'tools/probe_annotation_scope_runtime.tcl'),[str(root/'runtime.json')],root)
data=json.loads((root/'runtime.json').read_text(encoding='utf-8'));print(json.dumps(data,indent=2),flush=True)
