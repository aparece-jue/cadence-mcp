"""Preserve diagnostics for internal native occurrence-net discovery."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
config=Config(a.install_root,root/'work',(a.source.parent,),60)
before=sha256(a.source);target=root/'design.dsn';shutil.copyfile(a.source,target)
process=run_owned_process([str(config.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'inspect_occurrence_nets.tcl'),str(config.install_root),str(target),str(root/'native.json')],root,process_env(config),60)
report={'process':process,'sourceHashBefore':before,'sourceHashAfter':sha256(a.source),'copyUnchanged':sha256(target)==before,'passed':False}
if (root/'native.json').exists():
    data=json.loads((root/'native.json').read_text(encoding='utf-8'))
    report.update(occurrenceCount=data['occurrenceCount'],flatNetCount=data['flatNetCount'],pinCount=len(data['pins']))
report['passed']=process['state']=='exited' and process['returnCode']==0 and report['sourceHashAfter']==before and report['copyUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
