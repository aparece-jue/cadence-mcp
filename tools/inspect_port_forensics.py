import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-ports-20261027';target=root/'plan-1722585d50b14fbb97c407acaba1c82f/design.dsn';before=sha256(target)
s=(r/'tools/inspect_native_ports.tcl').read_text(encoding='utf-8');a='set name [cs ""];ck [$o GetName $name];';b='set nameState [DboState];set name [DboNetSymbolInstance_sGetNetName $o $nameState];ck $nameState;';assert s.count(a)==1;s=s.replace(a,b);(r/'tools/inspect_native_ports_netname.tcl').write_text(s,encoding='utf-8')
output=root/'forensic-ports-netname.json';config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'forensic-read-work',(root,),30)
try:run_tcl(config,str(r/'tools/inspect_native_ports_netname.tcl'),[str(target),str(output)],root)
finally:
 assert sha256(target)==before
 if output.exists():print(output.read_text(encoding='utf-8'),flush=True)
