import argparse,json,shutil,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.gui_loader import tcl_string
p=argparse.ArgumentParser(description='Fixed LowPassFilters private-INI/ALS provenance experiment; not a generic project generator.')
for name in ('install-root','workspace-root','source-root','native-netlist-root','global-ini'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];src=a.source_root.resolve(strict=True);root=a.workspace_root.resolve();assert '.local' in root.parts and '.local' in src.parts;root.mkdir(exist_ok=False)
project=root/'project';project.mkdir();source_before={p.relative_to(src).as_posix():sha256(p) for p in src.rglob('*') if p.is_file()}
for relative in ['lowpassfilters.dsn','LowPassFilters.opj','LowPassFilters-PSpiceFiles/LPFilters/AC.sim','LowPassFilters-PSpiceFiles/LPFilters/LPFilters.net']:
 target=project/relative;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(src/relative,target)
native=a.native_netlist_root.resolve(strict=True);native_report=json.loads((native/'report.json').read_text());assert native_report['sourceSha256']==sha256(src/'lowpassfilters.dsn') and sha256(native/'generated.net')==sha256(project/'LowPassFilters-PSpiceFiles/LPFilters/LPFilters.net');shutil.copyfile(native/'generated.als',project/'LowPassFilters-PSpiceFiles/LPFilters/LPFilters.als')
simdir=project/'LowPassFilters-PSpiceFiles/LPFilters';(simdir/'AC').mkdir();profile=simdir/'AC.sim';opj=project/'LowPassFilters.opj';library=root/'own-unused.lib';library.write_text('* Own unused model for explicit profile library provenance\n.MODEL MCP_UNUSED D(IS=1e-14)\n',encoding='ascii');ini=root/'private.ini';ini.write_text('[PSPICE NETLIST]\nLINE1=.lib "'+library.as_posix()+'"\nLINE2=.INC "'+r'..\LPFilters.als'+'"\n',encoding='ascii')
global_ini=a.global_ini.resolve(strict=True);global_before=sha256(global_ini);cfg=Config(a.install_root,root/'work',(root,),30)
nonce=uuid.uuid4().hex
cir=simdir/'AC/AC.cir'
code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\nsource '+tcl_string((ADAPTERS/'profile_circuit_job.tcl').as_posix())+'\n'
code+='::cmcpProfileCircuit::run '+' '.join(tcl_string(v.as_posix() if isinstance(v,Path) else v) for v in [cfg.install_root,opj,profile,ini,cir,root/'native-result.json',nonce])+'\n'
script=root/'probe.tcl';script.write_text(code,encoding='utf-8');proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script],root,process_env(cfg),30)
report={'passed':False,'scope':'Explicit private INI experiment, not original nominal-library AC acceptance','process':proc,'globalIniUnchanged':sha256(global_ini)==global_before,'sourceTreeUnchanged':all(sha256(src/name)==digest for name,digest in source_before.items()),'globalIniSha256':global_before,'sourceSha256':source_before,'privateIniSha256':sha256(ini),'librarySha256':sha256(library)}
if (root/'native-result.json').exists():report['receipt']=json.loads((root/'native-result.json').read_text())
cir=simdir/'AC/AC.cir';report['freshCirExists']=cir.exists()
if cir.exists():
 text=cir.read_text(encoding='utf-8');report['cirSha256']=sha256(cir);report['libraryLines']=[x.strip() for x in text.splitlines() if x.strip().lower().startswith('.lib ')];report['aliasSha256']=sha256(simdir/'LPFilters.als');report['aliasIncluded']=r'.INC "..\LPFilters.als"' in text;report['passed']=proc['state']=='exited' and proc['returnCode']==0 and report['receipt'].get('jobId')==nonce and report['receipt'].get('invocationReturned') is True and report['receipt'].get('phase')=='returned' and report['aliasIncluded'] and report['receipt'].get('updateResult')=='0' and report['libraryLines']==['.lib "'+library.as_posix()+'"'] and report['sourceTreeUnchanged'] and report['globalIniUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


if not report["passed"]:raise SystemExit(1)
