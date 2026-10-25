"""Native same-cell alternate-part diagrams, shared physical maps and package metadata."""
import argparse,copy,json
from pathlib import Path
from library_create_fixtures import specs
from library_variant_graphs import expected_variants,actual_variants
from cadence_mcp.core import Config,write_json,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.isolated_jobs import digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45);report={'passed':False,'scope':'native alternate-part OLB graph; no DSN instance or external footprint geometry certification','cases':[]}
for case,base in [('single','resistor'),('shared_dual','homogeneous_shared'),('heterogeneous_power','heterogeneous_power')]:
 d=root/case;d.mkdir();spec=copy.deepcopy(specs()[base]);spec['packageName']+='VAR';spec['footprint']+='VAR'
 # A Convert view reverses graphical x; logical positions/names/types remain exactly declared.
 for sym in list(spec['symbols']):
  if sym['cellName']=='POWER_CELL':continue
  alt=copy.deepcopy(sym);alt['partName']=sym['partName'].replace('.Normal','.Convert')
  for pin in alt['pins']:pin['start'][0]*=-1;pin['hotSpot'][0]*=-1
  for line in alt['lines']:line['start'][0]*=-1;line['end'][0]*=-1
  spec['symbols'].append(alt)
 write_json(d/'spec.json',spec);wanted=expected_variants(spec);write_json(d/'expected.json',wanted);row={'case':case,'passed':False,'expectedDigest':digest(wanted)};report['cases'].append(row)
 try:
  row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_library_variants.tcl'),str(cfg.install_root),str(d/'spec.json'),str(d/'library.olb'),str(d/'receipt.json')],d,process_env(cfg),45);row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']=={'saved':True,'operation':'create_library'},'native creation failed';before=sha256(d/'library.olb');row['savedSha256']=before
  run_tcl(cfg,'inspect_library_create.tcl',[str(d/'library.olb'),str(d/'actual.json'),'100000'],d);actual=actual_variants(json.loads((d/'actual.json').read_text()));row['actualDigest']=digest(actual);row['graphMatchesDeclared']=row['actualDigest']==row['expectedDigest'];row['logicalUnitCount']=len(spec['devices']);row['partVariantRows']=len(actual['devices']);row['pinViewRows']=len(actual['pins']);row['physicalPads']=len({p[6] for p in actual['pins']});row['outputUnchanged']=before==sha256(d/'library.olb');row['passed']=row['graphMatchesDeclared'] and row['outputUnchanged']
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case,row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
