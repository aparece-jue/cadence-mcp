"""Bounded native LIB path and nesting controls; original failed inputs stay immutable."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--fixture-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.output.resolve();root.mkdir(exist_ok=False);src=a.fixture_root/'inputs';files=list(src.iterdir())+[a.fixture_root/'expected.json'];before={str(f):sha256(f) for f in files if f.is_file()};report={'cases':{},'nativeNumericalAcceptance':False,'inputSha256':before};cfg=Config(a.install_root,root/'work',(root,),40)
for name in ('relative-nested','absolute-nested','relative-single','include-nested','absolute-long-nested','relative-long-nested'):
 case=root/name;case.mkdir();inputs=case/('padding-'+80*'x' if 'long' in name else 'inputs');inputs.mkdir();[shutil.copyfile(f,inputs/f.name) for f in src.iterdir() if f.suffix.lower() in ('.cir','.lib')];out=case/'output';out.mkdir();circuit=inputs/'divider.cir'
 if name in ('absolute-nested','absolute-long-nested'):
  circuit.write_text(circuit.read_text().replace('"outer models.lib"','"'+(inputs/'outer models.lib').as_posix()+'"'),encoding='utf8');outer=inputs/'outer models.lib';outer.write_text(outer.read_text().replace('"inner model.lib"','"'+(inputs/'inner model.lib').as_posix()+'"'),encoding='utf8')
 if name=='relative-single':circuit.write_text(circuit.read_text().replace('outer models.lib','inner model.lib'),encoding='utf8')
 if name=='include-nested':
  for f in list(inputs.iterdir()):f.write_text(f.read_text().replace('.LIB ','.INC '),encoding='utf8')
 result=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_analysis.tcl',a.install_root,circuit,out,'dc'],inputs,process_env(cfg),40)
 report['cases'][name]={'process':result,'phases':(out/'phases.log').read_text() if (out/'phases.log').exists() else None,'receipt':json.loads((out/'receipt.json').read_text()) if (out/'receipt.json').exists() else None,'inputLineLengths':[len(x) for x in circuit.read_text().splitlines()],'outputFiles':{f.name:f.stat().st_size for f in out.iterdir()}}
 print(json.dumps({name:report['cases'][name]}),flush=True)
report['originalInputsUnchanged']=all(sha256(Path(f))==v for f,v in before.items());(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');assert report['originalInputsUnchanged']
