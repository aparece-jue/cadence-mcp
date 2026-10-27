"""Read-only contrast of documented net-name API; never repeats bus construction."""
import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/editor-eight-bit-bus-20261027';root=r/'.local/editor-bus-netname-readonly-20261027';root.mkdir(exist_ok=False)
dispatch=json.loads((base/'dispatch-report.json').read_text(encoding='utf-8'));source=r/dispatch['jobDirectory']/'design.dsn';before=sha256(source)
text=(ADAPTERS/'inspect_bus.tcl').read_text(encoding='utf-8');text=text.replace('source [file join [file dirname [info script]] json.tcl]','source {'+(ADAPTERS/'json.tcl').as_posix()+'}')
assert text.count('$bus GetName $name')==1 and text.count('$member GetName $mn')==1
text=text.replace('$bus GetName $name','$bus GetNetName $name').replace('$member GetName $mn','$member GetNetName $mn');script=root/'inspect_bus_computed_names.tcl';script.write_text(text,encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),30);output=root/'bus.json';report={'passed':False,'sourceBefore':before,'nativeMutationReplayed':False,'changedGetter':'documented DboNet.GetNetName, not a status-ignoring fallback'}
report['process']=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,source,output],root,process_env(cfg),30)
if output.exists():
 data=json.loads(output.read_text(encoding='utf-8'));report['data']=data;report['passed']=True
if Path(str(output)+'.error.json').exists():report['error']=json.loads(Path(str(output)+'.error.json').read_text(encoding='utf-8'))
report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='data'}),flush=True)
