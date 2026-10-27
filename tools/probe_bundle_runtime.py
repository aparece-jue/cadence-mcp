import json
from pathlib import Path
from cadence_mcp.core import Config
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/bundle-runtime-20261027';root.mkdir(exist_ok=False)
config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),30)
run_tcl(config,str(r/'tools/probe_bundle_runtime.tcl'),[str(root/'runtime.json')],root)
data=json.loads((root/'runtime.json').read_text(encoding='utf-8'))
print(json.dumps(dict(variables=data['variables'],pointerHelpers=[name for name in data['commands'] if 'bool' in name.lower() or name.startswith('DboTclHelper_sMake')]),indent=2))
