"""Private diagnostic copy exposes native status codes; production reader stays unchanged."""
import argparse,json,subprocess
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(a.fixture_root,),45)
text=(ADAPTERS/'inspect.tcl').read_text(encoding='utf-8')
text=text.replace('[file dirname [info script]]','{'+ADAPTERS.as_posix()+'}')
assert 'error "DboState failure"' in text
text=text.replace('error "DboState failure"','error "DboState_[$state Code]"')
reader=root/'read-native-code.tcl';reader.write_text(text,encoding='utf-8');rows=[]
for mode in ('empty','direct','initial_design','initial_page','save_as','no_page_save'):
 source=a.fixture_root/mode/('final.dsn' if mode=='save_as' else 'design.dsn');before=sha256(source)
 process=subprocess.run([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(reader),str(cfg.install_root),str(source),str(root/(mode+'.json')),'100000'],cwd=root,env=process_env(cfg),capture_output=True,timeout=45)
 rows.append({'mode':mode,'returnCode':process.returncode,'stderr':process.stderr.decode('utf-8',errors='replace'),
              'sourceHash':before,'sourceUnchanged':sha256(source)==before})
report={'scope':'diagnostic status-code read only; source/production inspector unchanged','productionInspectorSha256':sha256(ADAPTERS/'inspect.tcl'),'rows':rows}
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
