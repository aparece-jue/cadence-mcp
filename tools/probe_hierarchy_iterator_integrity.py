import argparse,json,os,subprocess
from pathlib import Path
from hashlib import sha256
p=argparse.ArgumentParser()
for n in ('repo','install','source','root','harness'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--label',required=True)
a=p.parse_args();a.root.mkdir(exist_ok=False)
digest=lambda p:sha256(p.read_bytes()).hexdigest()
source=a.root/'design.dsn';source.write_bytes(a.source.read_bytes())
adapter=a.repo/'src/cadence_mcp/adapters/inspect_hierarchy.tcl'
frozen=a.root/'inspect_hierarchy.tcl';frozen.write_bytes(adapter.read_bytes());(a.root/'json.tcl').write_bytes((adapter.parent/'json.tcl').read_bytes())
env=os.environ.copy();env['PATH']=str(a.install/'tools/bin')+';'+env['PATH']
report={'label':a.label,'sourceBefore':digest(a.source),'copyBefore':digest(source),'adapterHash':digest(frozen),'cases':[]}
for mode in ('none','property','child'):
 output=a.root/(mode+'.json')
 child=subprocess.run([str(a.install/'tcltk/bin/tclsh.exe'),str(a.harness.resolve()),str(frozen.resolve()),str(a.install),str(source.resolve()),str(output.resolve()),mode],env=env,cwd=a.root,capture_output=True,timeout=60)
 (a.root/(mode+'.stdout')).write_bytes(child.stdout);(a.root/(mode+'.stderr')).write_bytes(child.stderr)
 row={'mode':mode,'exitCode':child.returncode,'outputExists':output.exists(),'injected':b'INJECTED:' in child.stderr}
 if output.exists():row['rows']=len(json.loads(output.read_text(encoding='utf-8')))
 row['acceptedExpected']=child.returncode==0 and output.exists() if mode=='none' else row['injected'] and child.returncode!=0 and not output.exists()
 report['cases'].append(row);print(json.dumps(row),flush=True)
report['sourceAfter']=digest(a.source);report['copyAfter']=digest(source);report['passed']=all(r['acceptedExpected'] for r in report['cases']) and report['sourceBefore']==report['sourceAfter'] and report['copyBefore']==report['copyAfter']
(a.root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
