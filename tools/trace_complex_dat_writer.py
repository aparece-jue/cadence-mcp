"""Trace the original owned2-block writer at native command boundaries."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','original-script'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
original=a.original_script.resolve(strict=True);before=sha256(original);text=original.read_text(encoding='utf-8')
needle='    orExprEval writer';assert needle in text
text=text.replace(needle,needle+'''\n    proc traceWriter {args} {note "TRACE $args"}
    trace add execution writer {enter leave} traceWriter''')
script=root/'trace-writer.tcl';script.write_text(text,encoding='utf-8');cfg=Config(a.install_root,root/'work',(root,),45)
directory=root/'fixture';directory.mkdir()
process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,directory],directory,process_env(cfg),45)
report={'scope':'private trace of original writer; no public API change','originalScriptSha256':before,'originalScriptUnchanged':sha256(original)==before,'process':process,'log':(directory/'fixture.log').read_text(encoding='utf-8') if (directory/'fixture.log').exists() else None}
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
