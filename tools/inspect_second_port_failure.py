import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1]
s=(r/'tools/recover_editor_ports_forensics_v2.py').read_text(encoding='utf-8').replace("root=r/'.local/editor-ports-20261027'","root=r/'.local/editor-ports-v2-20261027'")
compile(s,'recover_editor_ports_second.py','exec');(r/'tools/recover_editor_ports_second.py').write_text(s,encoding='utf-8')
