import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.pspice_input import PSpiceInputs
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','cir'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.cir.resolve(strict=True);before=sha256(source);library=a.install_root/'tools/pspice/library';service=PSpiceInputs(Config(a.install_root,root/'work',(source.parent.parent,library),60));result={'passed':False,'sourceSha256':before,'sourceUnchanged':False}
try:result['prepared']=service.prepare(str(source));result['passed']=True
except Exception as e:result.update(error=str(e),errorCode=getattr(e,'code',None))
result['sourceUnchanged']=sha256(source)==before;(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
