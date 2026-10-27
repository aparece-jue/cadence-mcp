"""Prepare one new private, independently readable editor command fixture."""
import json, shutil, subprocess
from pathlib import Path
from cadence_mcp.core import Config, sha256
from cadence_mcp.environment import run_tcl
from cadence_mcp.capture_pspice_project import parse_project, Node

r=Path(r'D:\workspace\git\cadence-mcp')
root=r/'.local/placewire-resume-v2-20261027'
root.mkdir(exist_ok=False)
source=r/'.local/editor-session-wire-20261026/before.dsn'
assert sha256(source)=='971c4675e25441783520afdd86a898647a39f05f377cc217d5e23c2bfb671dda'
target=root/'MCP_PLACE_WIRE.dsn'
shutil.copy2(source,target)
template=r/'.local/online-drc-all-rules-20261026/MCP_DRC_ALL_ONLINE.opj'
text=template.read_text(encoding='utf-8')
version=next(line for line in text.splitlines() if '(SoftwareVersion ' in line)
text='(ExpressProject "MCP_PLACE_WIRE"\n (ProjectVersion "19981106")\n'+version+'\n (ProjectType "PCB")\n (Folder "Design Resources" (Folder "Library") (NoModify) (File "./MCP_PLACE_WIRE.dsn" (Type "Schematic Design")))\n (Folder "Outputs")\n)\n'
parse_project(text)
(root/'MCP_PLACE_WIRE.opj').write_text(text,encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45)
run_tcl(cfg,'inspect.tcl',[str(target),str(root/'before-definitions.json'),'100000'],root)
run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(root/'before-connections.json'),'connections'],root)
defs=json.loads((root/'before-definitions.json').read_text(encoding='utf-8'))
assert [s['name'] for s in defs['schematic']]==['ROOT'] and [p['name'] for p in defs['page']]==['MAIN'] and not defs['part'] and not defs['pin']
assert not json.loads((root/'before-connections.json').read_text(encoding='utf-8'))['objects']
oracle={'schematics':['ROOT'],'pages':['MAIN'],'parts':0,'pins':0,'wires':[[[100,100],[300,100]]]}
(root/'expected.json').write_text(json.dumps(oracle,indent=2),encoding='utf-8')
report={'prepared':True,'sourceSha256':sha256(source),'targetBefore':sha256(target),'projectTemplateSha256':sha256(template),'scope':'PlaceWire 1,1,3,1 hypothesis; fixed DB endpoint oracle 100,100 to 300,100; no observation-derived oracle'}
(root/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
child=subprocess.Popen([str(cfg.install_root/'tools/bin/Capture.exe')],cwd=root)
(root/'host.json').write_text(json.dumps({'pid':child.pid,'executable':str(cfg.install_root/'tools/bin/Capture.exe')}),encoding='utf-8')
print(json.dumps({'newHostPid':child.pid}),flush=True)
