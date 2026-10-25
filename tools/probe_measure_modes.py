"""Compare official doALL/PSpiceDoAnalysis against original measurement fixtures."""
import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(r'D:\workspace\git\cadence-mcp');root=repo/'.local/native-measure-modes-20261025';root.mkdir(exist_ok=False)
install=Path(r'D:\Program Files\Cadence\SPB_24.1');old=repo/'.local/native-measure-20261023'
texts={name:(old/name/'input.cir').read_text(encoding='ascii') for name in ('dc','ac','transient')}
texts['ac-v-expression']=texts['ac'].replace('VM(2)','V(2)')
report={'scope':'official complete-analysis entry comparison, original failures retained','cases':[],'originalSourceHashes':{name:sha256(old/name/'input.cir') for name in ('dc','ac','transient')}}
for mode in ('doall','direct'):
 for name,text in texts.items():
  d=root/(mode+'-'+name);d.mkdir();c=d/'input.cir';c.write_text(text,encoding='ascii');before=sha256(c)
  cfg=Config(install,d/'work',(d,),45)
  row={'mode':mode,'case':name,'sourceSha256':before};report['cases'].append(row)
  row['process']=run_owned_process([install/'tcltk/bin/tclsh.exe',repo/'tools/probe_measure_modes.tcl',install,c,d,mode,ADAPTERS/'json.tcl'],d,process_env(cfg),45)
  if (d/'receipt.json').exists():row['receipt']=json.loads((d/'receipt.json').read_text(encoding='utf-8'))
  row['sourceUnchanged']=sha256(c)==before
  row['files']=[{'name':p.relative_to(d).as_posix(),'sha256':sha256(p),'size':p.stat().st_size} for p in d.rglob('*') if p.is_file()]
  row['extraText']={p.name:p.read_text(encoding='cp1252',errors='replace')[:12000] for p in d.iterdir() if p.is_file() and p.suffix.lower() not in ('.cir','.dat','.json')}
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(mode,name,row['process']['returnCode'],[p['name'] for p in row['files']],flush=True)
report['originalSourcesUnchanged']=report['originalSourceHashes']=={name:sha256(old/name/'input.cir') for name in ('dc','ac','transient')}
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
