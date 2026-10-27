"""Preserve original C04 oracle; prepare its global/offpage base without Dbo wires."""
import json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/c04-editor-matrix-base-20261027';root.mkdir(exist_ok=False)
old=r/'.local/connection-inventory-matrix-v2-20261025';oracle=old/'expected.json';assert sha256(oracle)=='d31c2041a595af1fb15e8af5813febf04376a0ba612bf8016c8651ebabcd4560'
shutil.copy2(oracle,root/'expected.json');shutil.copy2(old/'library.olb',root/'library.olb')
text=(r/'tools/fixture_connection_inventory.tcl').read_text(encoding='utf-8')
start=text.index('   foreach y {800 900} {');end=text.index('\n  }\n  ck [$page MarkModified]',start)
text=text[:start]+text[end:];script=r/'tools/fixture_connection_inventory_no_wires.tcl';assert not script.exists();script.write_text(text,encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45);source=root/'design.dsn';report={'passed':False,'originalOracleSha256':sha256(oracle)}
try:
 report['process']=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,root/'library.olb',source,root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45)
 assert report['process']['returnCode']==0;assert json.loads((root/'receipt.json').read_text(encoding='utf-8'))['saved']
 before=sha256(source)
 run_tcl(cfg,'inspect.tcl',[str(source),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_page_objects.tcl',[str(source),str(root/'connections.json'),'connections'],root)
 defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'));obj=json.loads((root/'connections.json').read_text(encoding='utf-8'))['objects']
 assert sorted(p['name'] for p in defs['page'])==['EMPTY','PAGE_A','PAGE_B'] and not defs['part'] and not defs['pin']
 counts={kind:sum(o['kind']==kind for o in obj) for kind in ('global','offpage','wire','alias')};assert counts=={'global':16,'offpage':16,'wire':0,'alias':0},counts
 assert sha256(source)==before;report.update(passed=True,sourceSha256=before,counts=counts,baseIndependentReopen=True)
except BaseException as error:report.update(error=str(error),errorCode=getattr(error,'code',None))
report['originalOracleUnchanged']=sha256(oracle)==sha256(root/'expected.json');(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
