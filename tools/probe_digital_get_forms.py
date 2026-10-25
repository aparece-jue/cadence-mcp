"""Private documented/sample get forms compared with independently known mixed data."""
import json, shutil
from pathlib import Path
from cadence_mcp.core import Config, sha256
from cadence_mcp.environment import process_env, ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(r'D:\workspace\git\cadence-mcp')
root=repo/'.local/digital-get-forms-20261025';root.mkdir(exist_ok=False)
fixture=json.loads((repo/'.local/mixed-dat-fixture-20261024/report.json').read_text(encoding='utf-8'))
assert fixture['passed']
source=Path(fixture['datPath']);original=sha256(source)
copied=root/'copied.dat';shutil.copyfile(source,copied)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45)
expected={'analogVolts':1,'digitalStimulus':[[0,'0'],[1e-6,'1'],[2e-6,'0'],[3e-6,'Z']],'digitalRows':5,'analogRows':58}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',repo/'tools/probe_digital_get_forms.tcl',cfg.install_root,copied,root/'native.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45)
report={'scope':'fixed documented get and installed analog QuickView getR/long-get sample comparison, not digital feature acceptance','process':process,'sourceBefore':original,'sourceAfter':sha256(source),'copyUnchanged':sha256(copied)==original,'expected':expected,'digitalAccepted':False}
if (root/'native.json').exists():report['calls']=json.loads((root/'native.json').read_text(encoding='utf-8'))
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'process':process,'sourceUnchanged':report['sourceBefore']==report['sourceAfter'],'calls':[{k:c[k] for k in ('call','caught','length')} for c in report.get('calls',[])]}))
