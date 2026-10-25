"""Owned original circuits producing distinct native diagnostic evidence."""
import json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_runs import PSpiceRuns
repo=Path(__file__).resolve().parents[1];root=repo/'.local/solver-diagnostics-probe-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
circuits={
 'nonconvergence':'* independent discontinuous no-solution equation\nVTEST TEST 0 DC 1\nRTEST TEST 0 1k\nE1 N 0 VALUE={IF(V(N)>0,-1,1)}\nR1 N 0 1k\n.NODESET V(N)=0.5\n.OPTIONS ITL1=5 ITL2=5\n.DC VTEST 1 1 1\n.PROBE\n.END\n',
 'undefined-model':'* independent unknown model\nV1 N 0 DC 1\nD1 N 0 UNKNOWN_MODEL_61\n.DC V1 1 1 1\n.PROBE\n.END\n',
 'voltage-loop':'* independent conflicting ideal voltage sources\nV1 N 0 DC 1\nV2 N 0 DC 2\nR1 N 0 1k\n.DC V1 1 1 1\n.PROBE\n.END\n'}
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(sources,),30);inputs=PSpiceInputs(cfg);runs=PSpiceRuns(cfg,inputs,PSpiceDat(cfg))
report={'scope':'native failure discovery; no license conclusion from timeout','cases':[]}
for name,text in circuits.items():
 source=sources/(name+'.cir');source.write_text(text,encoding='ascii');before=sha256(source)
 sid=inputs.prepare(str(source))['simulationId'];plan=runs.plan(sid,'dc',timeout_seconds=20)
 row={'case':name,'plan':plan};report['cases'].append(row)
 try:row['unexpectedResult']=runs.apply(plan['planId'],plan['planDigest'],name)
 except CadenceError as error:row['error']=error.code
 d,_,job=runs._load(plan['planId']);row['jobState']=job['state'];row['process']=job.get('process');row['sourceUnchanged']=sha256(source)==before
 if (d/'result.out').exists():row['out']=(d/'result.out').read_text(encoding='cp1252')
 if (d/'receipt.json').exists():row['receipt']=json.loads((d/'receipt.json').read_text(encoding='utf-8'))
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,row.get('error'),row.get('process'),flush=True)
