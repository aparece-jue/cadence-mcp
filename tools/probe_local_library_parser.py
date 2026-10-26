"""Fixed native local parseLib probe over a self-authored copied library, no engine/remote/server source."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);lib=root/'fixture.lib';lib.write_text('* original native parser fixture\n.MODEL D_META D(IS=1e-14)\n.SUBCKT RC_META IN OUT\nR1 IN OUT 1k\nC1 OUT 0 1u\n.ENDS RC_META\n.SUBCKT THREE_META A B C\nR1 A B 2k\nR2 B C 3k\n.ENDS THREE_META\n',encoding='utf-8');before=sha256(lib);cfg=Config(a.install_root,root/'work',(root,),60);result={'sourceSha256':before,'cases':[]}
for pins in (0,2,3):
 d=root/str(pins);d.mkdir();output=d/'receipt.json';proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_suffix('.tcl'),cfg.install_root,lib,str(pins),output],d,process_env(cfg),60);row={'pinCount':pins,'process':proc}
 if output.exists():
  receipt=json.loads(output.read_text(encoding='utf-8'));row['receipt']=receipt
  try:row['parsed']=json.loads(receipt['value'])
  except Exception:pass
 result['cases'].append(row);(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'pinCount':pins,'returnCode':proc['returnCode'],'receipt':row.get('receipt')}),flush=True)
result['sourceUnchanged']=sha256(lib)==before;(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
