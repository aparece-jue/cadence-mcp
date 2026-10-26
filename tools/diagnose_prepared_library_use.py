"""Read-only diagnosis of a prepared input's conservative library-use proof."""
import argparse,json,sys
from pathlib import Path
from cadence_mcp.core import CadenceError,sha256
from cadence_mcp.pspice_model_use import prove_unused_libraries
from cadence_mcp.pspice_runs import execution_preflight
p=argparse.ArgumentParser();p.add_argument('--prepared-directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.prepared_directory.resolve(strict=True);manifest_path=root/'input-manifest.json';before=sha256(manifest_path);manifest=json.loads(manifest_path.read_text(encoding='utf-8'));files={f['relativePath']:(root/f['relativePath']).read_bytes() for f in manifest['files']};events=[]
def trace(frame,event,arg):
 if event=='call' and frame.f_code.co_name=='fail' and frame.f_code.co_filename.endswith('pspice_model_use.py'):
  v=frame.f_back.f_locals;events.append({'file':v.get('name'),'physicalLine':v.get('number'),'kind':v.get('kind'),'depth':v.get('depth')})
 return trace
report={'proofAccepted':False,'manifestBefore':before};sys.settrace(trace)
try:report.update(proofAccepted=True,proof=prove_unused_libraries(root,files,manifest['files'],execution_preflight))
except CadenceError as error:report.update(proofAccepted=False,errorCode=error.code,refusals=events)
finally:sys.settrace(None)
report['manifestUnchanged']=sha256(manifest_path)==before
report['preparedBytesUnchanged']=all(sha256(root/f['relativePath'])==f['preparedSha256'] for f in manifest['files'])
with a.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
print(json.dumps(report))
