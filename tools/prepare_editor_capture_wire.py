"""Prepare a truly new blank DSN/OPJ; prove standalone readability before Capture host test."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);assert '.local' in root.parts;cfg=Config(a.install_root,root/'work',(root,),60);target=root/'MCP_VIEW_WIRE.dsn';output=root/'created.json';process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_blank_capture_wire.tcl'),cfg.install_root,target,output],root,process_env(cfg),60);report={'passed':False,'process':process}
try:
 assert process['returnCode']==0 and process['remainingOwnedProcesses']==0 and json.loads(output.read_text(encoding='utf-8'))['saved'];run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root);defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'));assert [s['name'] for s in defs['schematic']]==['ROOT'] and [s['name'] for s in defs['page']]==['MAIN'] and not defs['part'] and not defs['pin'];(root/'MCP_VIEW_WIRE.opj').write_text('(ExpressProject "MCP_VIEW_WIRE"\n (ProjectVersion "19981106")\n (ProjectType "Analog or A/D Mixed Mode")\n (Folder "Design Resources" (Folder "Library") (NoModify) (File ".\\\\MCP_VIEW_WIRE.dsn" (Type "Schematic Design")))\n)\n',encoding='utf-8');report.update(passed=True,sourceSha256=sha256(target));(root/'expected.json').write_text(json.dumps({'schematics':['ROOT'],'pages':['MAIN'],'parts':0,'pins':0,'wires':[[[100,100],[300,100]]]},indent=2),encoding='utf-8')
except Exception as e:report['error']=str(e)
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
