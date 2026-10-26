"""Freeze original DSN pin nodes and effective properties before export acceptance."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import read_design_properties
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source);cfg=Config(a.install_root,root,(source.parent,),60);cap=CaptureService(cfg);ws=cap.create_workspace(str(source));sid=cap.open(ws['workspaceId'])['sessionId']
try:
 data=cap.sessions[sid]['data'];parts={p['objectId']:p['reference'] for p in data['part']};pins=[{'reference':parts[p['partId']],'number':p['number'],'name':p['name'],'connected':p['connected'],'net':p['net']} for p in data['pin']];props=read_design_properties(cfg,cap.sessions[sid]['design'],cap.sessions[sid]['design'].parent)
 result={'scope':'original native DSN baseline before new netlist dispatch, not netlist-derived expectation','sourceFingerprint':before,'pins':pins,'properties':props,'sourceUnchanged':sha256(source)==before};assert result['sourceUnchanged'];(root/'oracle.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'pins':len(pins),'parts':len(props),'sourceUnchanged':True}),flush=True)
finally:cap.close(sid)
