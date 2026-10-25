"""Bounded positive/negative and missing-source bitmap byte oracles; no public feature promotion."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-a','source-b'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);repo=Path(__file__).resolve().parents[1]
source_a=a.source_a.resolve(strict=True);source_b=a.source_b.resolve(strict=True)
image=source_a/'pattern.bmp';hidden=source_a/'retained-pattern-for-closure.bmp'
assert image.resolve().is_relative_to(repo/'.local') and hidden.resolve().is_relative_to(repo/'.local')
assert not hidden.exists()
shutil.copyfile(image,root/'expected-A.bmp');shutil.copyfile(source_b/'pattern.bmp',root/'expected-B.bmp')
before={str(p):sha256(p) for p in (source_a/'library.olb',source_b/'library.olb',image,source_b/'pattern.bmp')}
oracle={'A':hashlib.sha256((root/'expected-A.bmp').read_bytes()[14:]).hexdigest(),'B':hashlib.sha256((root/'expected-B.bmp').read_bytes()[14:]).hexdigest()}
assert oracle['A']!=oracle['B'];write_json(root/'expected.json',oracle);oracle_hash=sha256(root/'expected.json')
cfg=Config(a.install_root,root/'work',(source_a,source_b,root),60);report={'passed':False,'scope':'private embedded-Tcl DIB-byte prototype; public bitmap create/query/edit/place remains unavailable','checks':{}}
def probe(label,library,expected):
 output=root/(label+'.json')
 process=run_owned_process([sys.executable,str(repo/'tools/probe_bitmap_bytes.py'),'--install-root',str(cfg.install_root),'--library',str(library),'--expected-bmp',str(expected),'--output',str(output)],root,process_env(cfg),60)
 result=json.loads(output.read_text(encoding='utf-8'));report[label]={'process':process,'result':result}
 assert process['state']=='exited' and process['remainingOwnedProcesses']==0 and process['rootExitSignalConfirmed']
 return process,result
try:
 process,result=probe('positive-A',source_a/'library.olb',root/'expected-A.bmp')
 assert process['returnCode']==0 and result['passed'] and result['dibSha256']==oracle['A']
 process,result=probe('positive-B',source_b/'library.olb',root/'expected-B.bmp')
 assert process['returnCode']==0 and result['passed'] and result['dibSha256']==oracle['B']
 report['checks']['two_independent_pixel_payloads_match']=True
 process,result=probe('wrong-expected',source_a/'library.olb',root/'expected-B.bmp')
 assert process['returnCode']==1 and not result['passed'] and result['bytesMatchIndependentBmpDib'] is False
 assert result['dibSha256']==oracle['A'] and result['expectedDibSha256']==oracle['B'] and result['sourceUnchanged']
 report['checks']['same_geometry_different_pixels_refused']=True
 # Move only this run's own source image, after checking both absolute paths remain in .local.
 image.rename(hidden)
 try:
  assert not image.exists()
  process,result=probe('missing-source-image',source_a/'library.olb',root/'expected-A.bmp')
  assert process['returnCode']==0 and result['passed'] and result['dibSha256']==oracle['A'] and not image.exists()
  report['checks']['fresh_read_without_original_bmp']=True
 finally:
  assert not image.exists();hidden.rename(image)
 report['sourcesAndOracleUnchanged']=all(sha256(Path(p))==h for p,h in before.items()) and sha256(root/'expected.json')==oracle_hash
 report['passed']=report['sourcesAndOracleUnchanged'] and all(report['checks'].values())
except BaseException as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
