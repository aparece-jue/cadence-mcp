import json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-hierarchy-scaffold-20261027';root.mkdir(exist_ok=False)
s=(r/'src/cadence_mcp/adapters/fixture_hierarchy_ports.tcl').read_text(encoding='utf-8').replace('[file dirname [info script]] json.tcl','[file dirname [info script]] .. src cadence_mcp adapters json.tcl')
start=s.index(' set phase create_port_symbols');end=s.index(' set phase create_parent_block',start);s=s[:start]+s[end:]
start=s.index(' set phase save_symbols');end=s.index(' set phase save_child',start);s=s[:start]+s[end:]
(r/'tools/fixture_hierarchy_scaffold.tcl').write_text(s,encoding='utf-8')
original=r/'.local/hierarchy-fresh-ports-v2-20261023/expected.json';frozen=original.read_bytes();(root/'original-expected.json').write_bytes(frozen);cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),30);report=dict(passed=False,originalOracleSha256=sha256(original),fullH03Accepted=False)
try:
 run_tcl(cfg,str(r/'tools/fixture_hierarchy_scaffold.tcl'),[str(root/'design.dsn'),str(root/'native-result.json')],root)
 run_tcl(cfg,'inspect.tcl',[str(root/'design.dsn'),str(root/'definitions.json'),'100000'],root)
 data=json.loads((root/'definitions.json').read_text(encoding='utf-8'));counts={k:len(v) for k,v in data.items()};assert counts==dict(schematic=2,page=2,part=1,pin=2),counts;assert {s['name'] for s in data['schematic']}=={'TOP','CHILD'};assert data['part'][0]['reference']=='BLOCK_A'
 report.update(passed=True,counts=counts,sourceSha256=sha256(root/'design.dsn'),independentReopen=True)
except BaseException:report['error']=traceback.format_exc()
report['originalOracleUnchanged']=sha256(original)==report['originalOracleSha256'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
