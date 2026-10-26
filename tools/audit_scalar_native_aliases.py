import argparse,json,re
from pathlib import Path
from cadence_mcp.core import sha256
p=argparse.ArgumentParser(description='Audit scalar native ALS against a source-DSN pin table frozen before export.')
for name in ('workspace-root','oracle','native-aliases','copied-aliases'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);oracle=a.oracle.resolve(strict=True);o=json.loads(oracle.read_text(encoding='utf-8'));original=a.native_aliases.resolve(strict=True);copied=a.copied_aliases.resolve(strict=True);
before={str(p):sha256(p) for p in [oracle,original,copied]};assert sha256(original)==sha256(copied);expected={}
for p in o['pins']:
 label=p['name'] if p['reference'].upper().startswith('V') else p['number'];expected.setdefault(p['reference'],{})[label]=p['net']
def check(text):
 lines=[line.strip() for line in text.splitlines() if line.strip()];assert lines[0]=='.ALIASES' and lines[-1]=='.ENDALIASES';actual={}
 for line in lines[1:-1]:
  m=re.fullmatch(r'([RCLV]_[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\(([^()]*)\)\s+CN\s+\S+',line);assert m;device,ref,values=m.groups();assert device[2:]==ref and ref not in actual;tokens=values.split();mapping={}
  for item in tokens:
   pin,node=item.split('=');assert pin not in mapping;mapping[pin]=node
  actual[ref]=mapping
 assert actual==expected
 return actual
text=original.read_text(encoding='utf-8');mapping=check(text);negatives={
'wrong_node':text.replace('1=N00525','1=0',1),'wrong_voltage_polarity':text.replace('+=N00525 -=0','+=0 -=N00525',1),'missing_component':'\n'.join(line for line in text.splitlines() if not line.startswith('L_L1')),'duplicate_component':text.replace('.ENDALIASES',text.splitlines()[1]+'\n.ENDALIASES')}
for name,bad in negatives.items():
 assert bad!=text
 try:check(bad)
 except (AssertionError,ValueError):continue
 raise AssertionError('Accepted negative '+name)
assert all(sha256(Path(p))==digest for p,digest in before.items());report={'passed':True,'scope':'Original seven scalar parts and14 frozen source-DSN pins match native ALS, private copied ALS identical; not all Capture alias formats','mapping':mapping,'negativeCasesRejected':list(negatives),'fingerprints':before,'fullV04Accepted':False,'fullP05Accepted':False};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':True,'parts':len(mapping),'pins':sum(map(len,mapping.values())),'negativeCases':len(negatives)}))
