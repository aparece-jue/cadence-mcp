"""Independent source-naming/visibility comparison; original libraries stay immutable."""
import argparse,copy,json
from pathlib import Path
from library_variant_graphs import expected_variants,actual_variants
from cadence_mcp.core import Config,write_json,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.isolated_jobs import digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60)
report={'passed':False,'scope':'naming/visibility OLB graph comparison; not DSN electrical acceptance','cases':[]}
for mode in ('hidden','visible'):
 for case in ('shared_dual','heterogeneous_power'):
  d=root/mode/case;d.mkdir(parents=True);original=a.source_root/case/'spec.json';original_hash=sha256(original);spec=copy.deepcopy(json.loads(original.read_text()))
  cells={s['cellName'] for s in spec['symbols']};mapping={c:spec['packageName']+('_'+c if len(cells)>1 else '') for c in cells}
  for s in spec['symbols']:
   old=s['cellName'];s['cellName']=mapping[old];s['partName']=mapping[old]+'.'+s['partName'].rsplit('.',1)[-1]
   if mode=='visible':
    for pin in s['pins']:
     if pin['name'] in ('VCC','GND'):pin['visible']=True
  for dev in spec['devices']:dev['cellName']=mapping[dev['cellName']]
  write_json(d/'spec.json',spec);wanted=expected_variants(spec);write_json(d/'expected.json',wanted);row={'case':case,'mode':mode,'passed':False,'expectedDigest':digest(wanted),'originalSpecSha256':original_hash};report['cases'].append(row)
  try:
   row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'create_library.tcl'),str(cfg.install_root),str(d/'spec.json'),str(d/'library.olb'),str(d/'receipt.json')],d,process_env(cfg),60)
   row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']['saved'];before=sha256(d/'library.olb')
   run_tcl(cfg,'inspect_library_create.tcl',[str(d/'library.olb'),str(d/'actual.json'),'100000'],d);actual=actual_variants(json.loads((d/'actual.json').read_text()));row['graphMatches']=digest(actual)==digest(wanted);row['outputUnchanged']=sha256(d/'library.olb')==before;row['originalSpecUnchanged']=sha256(original)==original_hash;row['passed']=row['graphMatches'] and row['outputUnchanged'] and row['originalSpecUnchanged'] and row['process']['remainingOwnedProcesses']==0
  except Exception as e:row['error']=str(e)
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(mode,case,row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)

