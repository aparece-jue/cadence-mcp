import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.library_create import expected_graph,actual_graph,validate_spec
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','boundary-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);config=Config(a.install_root.resolve(),root/'work',(root,),60);oracle=a.boundary_root/'expected.json';spec=json.loads(oracle.read_text(encoding='utf-8'))['pin_name_boundaries'];checked=copy.deepcopy(spec)
# Private native reproduction intentionally tests unsupported empty names; all other fields stay validated.
for symbol in checked['symbols']:
 for pin in symbol['pins']:
  if pin['name']=='':pin['name']='PROBE_EMPTY'
validate_spec(checked);expected=expected_graph(spec);before=sha256(oracle);report={'passed':False,'oracleBefore':before,'cases':[]}
for label,methods in [('set_pin_name',['SetPinName']),('set_name',['SetName']),('both',['SetPinName','SetName'])]:
 d=root/label;d.mkdir();(d/'spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
 for name in ('json.tcl','dbo_create_vector.tcl'):shutil.copy2(ADAPTERS/name,d/name)
 script=(ADAPTERS/'create_library.tcl').read_text(encoding='utf-8');anchor='            if {$object eq "NULL"} {error missing_pin}';assert script.count(anchor)==1
 insertion='\n            if {[dict get $pin name] eq ""} {'+''.join('cmcp::check [$object '+method+' [cmcp::cs ""]];' for method in methods)+'}'
 (d/'create.tcl').write_text(script.replace(anchor,anchor+insertion),encoding='utf-8');row={'case':label,'passed':False};report['cases'].append(row)
 try:
  row['process']=run_owned_process([config.install_root/'tcltk/bin/tclsh.exe',d/'create.tcl',config.install_root,d/'spec.json',d/'library.olb',d/'receipt.json'],d,process_env(config),60);assert row['process']['returnCode']==0,row['process']
  run_tcl(config,'inspect_library_create.tcl',[str(d/'library.olb'),str(d/'actual.json'),'100000','0'],d);actual=actual_graph(json.loads((d/'actual.json').read_text(encoding='utf-8')));row['pin0']=next(p for p in actual['pins'] if p[5]==0);row['passed']=actual==expected
 except BaseException as e:row.update(error=str(e),errorCode=getattr(e,'code',None))
 print(json.dumps({'case':label,'passed':row['passed'],'pin0':row.get('pin0'),'error':row.get('error')},ensure_ascii=False),flush=True)
report['oracleUnchanged']=sha256(oracle)==before;report['passed']=all(c['passed'] for c in report['cases']) and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
