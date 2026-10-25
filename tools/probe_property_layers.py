import json
from pathlib import Path
from cadence_mcp.core import Config
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_property_layers import read_property_layers
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(__file__).resolve().parents[1];root=repo/'.local/property-layers-probe-v4-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(sources,),60);capture=CaptureService(cfg);report={'cases':[]}
expected={'default':'库默认值','override':'显式覆盖','local':'料号[x]$;"\\\n尾','displayLocation':[13,17]}
(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8')
for mode in ('base','override','empty','deleted'):
 row={'case':mode};report['cases'].append(row)
 try:
  source=sources/(mode+'.dsn');row['process']=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',repo/'tools/fixture_property_layers.tcl',cfg.install_root,source,mode,sources/(mode+'.json'),ADAPTERS/'json.tcl'],sources,process_env(cfg),60)
  assert row['process']['returnCode']==0
  ws=capture.create_workspace(str(source));opened=capture.open(ws['workspaceId']);session=capture.sessions[opened['sessionId']];schematics={s['objectId']:s['name'] for s in session['data']['schematic']}
  row['layers']=[]
  for part in session['data']['part']:
   layer=read_property_layers(capture,opened['sessionId'],part['objectId']);layer['schematicResolved']=schematics[part['schematicId']];row['layers'].append(layer)
  capture.close(opened['sessionId']);row['readPassed']=True
 except BaseException as error:
  import traceback
  row.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(mode, [{k:l[k] for k in ('schematicResolved','reference','user','display')} for l in row.get('layers',[]) if l['reference']=='R1'],row.get('error'),flush=True)
