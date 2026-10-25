"""Official ReadAllPages/Expand memory initialization on frozen failed fixtures."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','cross-page-source','port-source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45);report={'scope':'documented in-memory schematic loading/expansion; no save','cases':[]}
for kind,source,original in [('cross',a.cross_page_source,'inspect_cross_page.tcl'),('port-bindings',a.port_source,'inspect_net_symbol_bindings.tcl')]:
 source=source.resolve(strict=True);before=sha256(source)
 for mode in ('read_all','expand'):
  d=root/(kind+'-'+mode);d.mkdir();out=d/'output.json';s=(ADAPTERS/original).read_text(encoding='utf-8')
  initialize='cmcp::check [$sch ReadAllPages];'+('cmcp::check [$sch Expand];' if mode=='expand' else '')
  if kind=='cross':s=s.replace('set ro [$d GetRootOccurrence',initialize+'set ro [$d GetRootOccurrence')
  else:s=s.replace('set pi [$s NewPagesIter','cmcp::check [$s ReadAllPages];'+('cmcp::check [$s Expand];' if mode=='expand' else '')+'set pi [$s NewPagesIter')
  s=s.replace('source [file join [file dirname [info script]] json.tcl]', 'source {'+str(ADAPTERS/'json.tcl').replace('\\','/')+'}')
  script=d/'reader.tcl';script.write_text(s,encoding='utf-8');args=[str(source),'plain',str(out)] if kind=='cross' else [str(source),str(out)]
  row={'kind':kind,'mode':mode,'sourceBefore':before};report['cases'].append(row);row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(script),str(cfg.install_root),*args],d,process_env(cfg),45)
  row['outputExists']=out.exists();row['sourceUnchanged']=sha256(source)==before
  if out.exists():row['rows']=len(json.loads(out.read_text()))
  if Path(str(out)+'.error.json').exists():row['nativeError']=json.loads(Path(str(out)+'.error.json').read_text())
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
