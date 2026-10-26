"""Generate CIR from a copied profile and previously source-audited native NET, no solver/remote dispatch."""
import argparse,json,re,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source-root','netlist-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);src=a.source_root.resolve();netroot=a.netlist_root.resolve();assert '.local' in root.parts and '.local' in src.parts and '.local' in netroot.parts
source=src/'lowpassfilters.dsn';before=sha256(source);net=netroot/'generated.net';report=json.loads((netroot/'report.json').read_text(encoding='utf-8'));assert report['sourceUnchanged'] and report['sourceSha256']==before
folder=root/'project';folder.mkdir();target=folder/'lowpassfilters.dsn';shutil.copy2(source,target);project=folder/'LowPassFilters.opj';text=(src/'LowPassFilters.opj').read_text(encoding='utf-8');text=re.sub(r'\(Path "[A-Za-z]:[^"]*\.DSN"\)',lambda m:'(Path "'+target.as_posix()+'")',text,flags=re.I);project.write_text(text,encoding='utf-8');simdir=folder/'LowPassFilters-PSpiceFiles/LPFilters';simdir.mkdir(parents=True);(simdir/'AC').mkdir();profile=simdir/'AC.sim';shutil.copy2(src/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim',profile);shutil.copy2(net,simdir/'LPFilters.net');cfg=Config(a.install_root,root/'work',(src,),60);output=root/'native-result.json';marker=root/'phases.txt';proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_suffix('.tcl'),cfg.install_root,project,profile,output,marker],root,process_env(cfg),60);result={'passed':False,'process':proc,'sourceSha256':before,'netSha256':sha256(net),'sourceUnchanged':sha256(source)==before,'phases':marker.read_text(encoding='utf-8').splitlines() if marker.exists() else []}
if output.exists():result['receipt']=json.loads(output.read_text(encoding='utf-8'))
result['cirFiles']=[{'path':f.relative_to(root).as_posix(),'sha256':sha256(f),'size':f.stat().st_size} for f in root.rglob('*') if f.is_file() and f.suffix.lower()=='.cir'];result['passed']=proc['returnCode']==0 and result['sourceUnchanged'] and len(result['cirFiles'])==1 and result.get('receipt',{}).get('invocationReturned',False) and result['receipt'].get('updateResult')=='0' and proc['remainingOwnedProcesses']==0;(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
