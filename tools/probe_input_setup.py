"""Native setup-only checks on original valid and deliberately invalid CIR inputs."""
import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(__file__).resolve().parents[1];root=repo/'.local/input-setup-probe-20261025';root.mkdir(exist_ok=False)
cases={
 'valid':'* original valid parameter divider\n.PARAM RVAL=1k\nV1 1 0 DC 5\nR1 1 2 {RVAL}\nR2 2 0 {RVAL}\n.DC V1 5 5 1\n.PROBE\n.END\n',
 'missing-ground':'* original floating circuit\nV1 A B DC 5\nR1 A B 1k\n.DC V1 5 5 1\n.PROBE\n.END\n',
 'undefined-parameter':'* original undefined parameter\nV1 1 0 DC 5\nR1 1 0 {MISSING_PARAMETER_64}\n.DC V1 5 5 1\n.PROBE\n.END\n',
 'bad-analysis':'* original incomplete DC statement\nV1 1 0 DC 5\nR1 1 0 1k\n.DC V1 5\n.PROBE\n.END\n',
 'undefined-model':'* original missing model\nV1 1 0 DC 5\nD1 1 0 MISSING_MODEL_64\n.DC V1 5 5 1\n.PROBE\n.END\n'}
report={'scope':'private parser/setup-only probe; no numerical analysis','cases':[]}
for name,text in cases.items():
 d=root/name;d.mkdir();source=d/'input.cir';source.write_text(text,encoding='ascii');before=sha256(source);cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),d/'work',(d,),30)
 process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',repo/'tools/check_input_probe.tcl',cfg.install_root,source,d,ADAPTERS/'json.tcl'],d,process_env(cfg),30)
 row={'case':name,'process':process,'sourceUnchanged':sha256(source)==before};report['cases'].append(row)
 if (d/'receipt.json').exists():row['receipt']=json.loads((d/'receipt.json').read_text(encoding='utf-8'))
 if (d/'result.out').exists():row['out']=(d/'result.out').read_text(encoding='cp1252')
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,process['returnCode'],row.get('receipt'),flush=True)
