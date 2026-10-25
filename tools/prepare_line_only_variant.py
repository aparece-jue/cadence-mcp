"""Native fixture with identical pin signatures and distinct declared line drawings."""
import argparse,copy,json
from pathlib import Path
from library_variant_graphs import expected_variants,actual_variants
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.isolated_jobs import digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60);source=a.source_root/'spec.json';before=sha256(source);spec=copy.deepcopy(json.loads(source.read_text(encoding='utf-8')));normal=next(s for s in spec['symbols'] if s['partName'].endswith('.Normal'));convert=next(s for s in spec['symbols'] if s['partName'].endswith('.Convert'));convert['pins']=copy.deepcopy(normal['pins']);convert['lines']=copy.deepcopy(normal['lines'])+[{'start':[-8,-4],'end':[8,4],'style':0,'width':0}];write_json(root/'spec.json',spec);expected=expected_variants(spec);write_json(root/'expected.json',expected);process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'create_library.tcl'),str(cfg.install_root),str(root/'spec.json'),str(root/'library.olb'),str(root/'receipt.json')],root,process_env(cfg),60);assert process['returnCode']==0
saved=sha256(root/'library.olb');run_tcl(cfg,'inspect_library_create.tcl',[str(root/'library.olb'),str(root/'actual.json'),'100000'],root);actual=actual_variants(json.loads((root/'actual.json').read_text()));report={'passed':digest(actual)==digest(expected) and sha256(source)==before and sha256(root/'library.olb')==saved and process['remainingOwnedProcesses']==0,'process':process,'sourceSpecSha256':before,'savedSha256':saved,'identicalPins':normal['pins']==convert['pins'],'lineCounts':[len(normal['lines']),len(convert['lines'])]};write_json(root/'report.json',report);print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
