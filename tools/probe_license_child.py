"""Child-local documented license endpoint override; never modify parent/global settings."""
import json,os,socket,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(__file__).resolve().parents[1];root=repo/'.local/license-child-probe-20261025';root.mkdir(exist_ok=False)
original=repo/'.local/pspice-owned-7797dd67a5/source/divider.cir';before=sha256(original);parent=dict(os.environ)
report={'scope':'documented CDS_LIC_FILE override only in child environment; no real server/global/license-file changes','cases':[],'nativeUnavailableLicenseVerified':False}
with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as reserved:
 reserved.bind(('127.0.0.1',0));endpoint=str(reserved.getsockname()[1])+'@127.0.0.1'
 # Bound but not listening: this private loopback port cannot be an accidental license server.
 for backend in ('cli','engine-setup','control-cli'):
  d=root/backend;d.mkdir();source=d/'input.cir';shutil.copyfile(original,source);cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),d/'work',(d,),30);env=process_env(cfg)
  if backend!='control-cli':env['CDS_LIC_FILE']=endpoint
  cmd=[cfg.install_root/'tools/bin/psp_cmd.exe','/r',source] if backend!='engine-setup' else [cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'check_pspice_input.tcl',cfg.install_root,source,d,ADAPTERS/'json.tcl']
  process=run_owned_process([str(x) for x in cmd],d,env,20)
  row={'backend':backend,'childLicenseEndpointOverridden':backend!='control-cli','process':process,'sourceUnchanged':sha256(source)==before,'files':[{'name':p.name,'sha256':sha256(p),'size':p.stat().st_size} for p in d.rglob('*') if p.is_file()]};report['cases'].append(row)
  for p in d.iterdir():
   if p.is_file() and p.suffix.lower() in ('.out','.json','.log'):row[p.name]=p.read_text(encoding='cp1252',errors='replace')[:16000]
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(backend,process['state'],process['returnCode'],[p['name'] for p in row['files']],flush=True)
report['parentEnvironmentUnchanged']=parent==dict(os.environ);report['originalSourceUnchanged']=sha256(original)==before
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
