import argparse,json,shutil,struct
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-library'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--variant',choices=('a','b','shifted'),default='a')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_library.resolve(strict=True);before=sha256(source)
pixels=bytes([255,0,0,255,255,255,0,0,0,0,255,0,255,0,0,0])
if a.variant=='b':pixels=bytes(255-v for v in pixels)
dib=struct.pack('<IiiHHIIiiII',40,2,2,1,24,0,16,0,0,0,0)+pixels
bmp=b'BM'+struct.pack('<IHHI',14+len(dib),0,0,54)+dib
(root/'pattern.bmp').write_bytes(bmp);shutil.copyfile(source,root/'library.olb')
(root/'expected.json').write_text(json.dumps({'bounds':[0,0,20,20],'location':[0,0],'dimensions':[2,2],'dibSize':len(dib),'sourceImageSha256':sha256(root/'pattern.bmp')},indent=2),encoding='utf-8')
cfg=Config(a.install_root,root,(root,),60);report={'passed':False,'scope':'private native bitmap construction/reopen fields; image identity is not yet certified'}
try:
 for mode in (('create_shifted' if a.variant=='shifted' else 'create'),'read'):
  output=root/(mode+'.json');process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'probe_bitmap_fixture.tcl'),str(cfg.install_root),str(root/'library.olb'),str(root/'pattern.bmp'),str(output),mode],root,process_env(cfg),60)
  report[mode+'Process']=process;report[mode]=json.loads(output.read_text(encoding='utf-8'))
  assert process['returnCode']==0 and process['remainingOwnedProcesses']==0 and report[mode]['succeeded']
 report['sourceUnchanged']=sha256(source)==before
 report['rawDibOccurrencesInSavedLibrary']=(root/'library.olb').read_bytes().count(dib)
 expected={'index':13,'bounds':[0,0,20,20],'location':[0,0],'dimensions':[2,2],'dibSize':len(dib)}
 report['declaredFieldsMatch']=report['create_shifted' if a.variant=='shifted' else 'create']['bitmaps']==[expected] and report['read']['bitmaps']==[expected]
 report['passed']=report['sourceUnchanged'] and report['declaredFieldsMatch']
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
raise SystemExit(0 if report['passed'] else 1)
