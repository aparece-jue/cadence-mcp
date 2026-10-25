import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60);source=cfg.install_root/'tools/capture/library/capsym.olb';before=sha256(source);copy=root/'capsym.olb';shutil.copyfile(source,copy);report={'passed':False,'originalSha256Before':before}
try:
 out=root/'symbols.json';run_tcl(cfg,'inspect_net_symbols.tcl',[str(copy),str(out)],root);symbols=json.loads(out.read_text());report.update(passed=True,symbols=symbols)
except Exception as e:report['error']=str(e)
report.update(originalSha256After=sha256(source),copySha256After=sha256(copy));report['passed'] &= report['originalSha256After']==before==report['copySha256After'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
