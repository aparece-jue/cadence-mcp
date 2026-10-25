"""Official noninteractive executable only; fresh owned outputs and stopped process proof."""
import json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
repo=Path(__file__).resolve().parents[1];root=repo/'.local/official-cli-recheck-20261025';root.mkdir(exist_ok=False)
original=repo/'.local/pspice-owned-7797dd67a5/source/divider.cir';before=sha256(original);install=Path(r'D:\Program Files\Cadence\SPB_24.1')
report={'scope':'official psp_cmd noninteractive recheck; no GUI executable or license conclusion from timeout','originalSourceBefore':before,'cases':[]}
expected={'node':'2','volts':2.5,'absoluteTolerance':1e-6};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
for name in ('run-exit-explicit','original-run'):
 d=root/name;d.mkdir();source=d/'input.cir';shutil.copyfile(original,source);cfg=Config(install,d/'work',(d,),60)
 args=[install/'tools/bin/psp_cmd.exe','/r']
 if name=='run-exit-explicit':args+=['/e','/o',d/'result.out','/d',d/'result.dat','/l',d/'session.log']
 args+=[source];process=run_owned_process([str(x) for x in args],d,process_env(cfg),30)
 row={'case':name,'command':[str(x) for x in args],'process':process,'sourceUnchanged':sha256(source)==before,'files':[{'name':p.name,'sha256':sha256(p),'size':p.stat().st_size} for p in d.rglob('*') if p.is_file()]};report['cases'].append(row)
 for p in d.glob('*'):
  if p.is_file() and p.suffix.lower() in ('.out','.log'):row[p.name]=p.read_text(encoding='cp1252',errors='replace')[:16000]
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,process,[p['name'] for p in row['files']],flush=True)
report['originalSourceAfter']=sha256(original);assert report['originalSourceAfter']==before
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
