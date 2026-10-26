"""Compare scalar R/C/L/V NET against a DSN oracle frozen before that export."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('oracle','netlist-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);oracle=json.loads(a.oracle.read_text(encoding='utf-8'));netroot=a.netlist_root.resolve();native=json.loads((netroot/'report.json').read_text(encoding='utf-8'));target=netroot/'generated.net';before=sha256(target);oracle_hash=sha256(a.oracle)
assert native['acknowledged'] and native['receipt']['invocationReturned'] and native['receipt']['nativeReturn']=='1' and native['sourceUnchanged'] and native['oracleUnchanged'] and native['oracleSha256']==oracle_hash and native['sourceSha256']==oracle['sourceFingerprint']
assert not next(x for x in native['receipt']['logs'] if x['category']=='errors')['lines']
pins=oracle['pins'];assert len(pins)==14 and all(p['connected'] and p['net'] for p in pins);props={r['scope'][-1].casefold():{p['name']:p['value'] for p in r['properties']} for r in oracle['properties']};by_ref={}
for pin in pins:by_ref.setdefault(pin['reference'].casefold(),[]).append(pin)
assert len(by_ref)==7 and len(props)==7

def compare(text):
 observed={};rows=[]
 for line in text.splitlines():
  if not line.strip() or line.lstrip().startswith('*'):continue
  tokens=line.split();name=tokens[0]
  if len(tokens)<4 or len(name)<3 or name[0] not in 'RCLV' or name[1]!='_':raise ValueError('unsupported scalar line')
  kind=name[0];ref=name[2:].casefold()
  if ref not in by_ref or ref in observed:raise ValueError('missing/duplicate/foreign component')
  pr=props[ref];template=pr['PSpiceTemplate'].upper()
  if kind in 'RCL':
   if not template.startswith(kind+'^@REFDES %1 %2'):raise ValueError('unsupported pin template')
   numbers=['1','2']
   if tokens[3].casefold()!=pr['Value'].casefold():raise ValueError('component value mismatch')
   if kind in 'RC' and tokens[4:]!=['TC='+pr['TC1']+','+pr['TC2']]:raise ValueError('temperature coefficients mismatch')
   if kind=='L' and len(tokens)!=4:raise ValueError('unexpected inductor fields')
  else:
   if not template.startswith('V^@REFDES %+ %-'):raise ValueError('unsupported voltage template')
   numbers=[]
   for name in ('+','-'):
    matching=[p['number'] for p in by_ref[ref] if p['name']==name]
    if len(matching)!=1:raise ValueError('voltage pin mapping')
    numbers.extend(matching)
   if pr.get('ACPHASE','')!='' or len(tokens)!=7 or tokens[3].upper()!='DC' or tokens[5].upper()!='AC' or tokens[4].casefold()!=pr['DC'].casefold() or tokens[6].casefold()!=pr['ACMAG'].casefold():raise ValueError('voltage parameters mismatch')
  nodes={p['number']:p['net'].casefold() for p in by_ref[ref]}
  if len(nodes)!=2 or [nodes[n] for n in numbers]!=[x.casefold() for x in tokens[1:3]]:raise ValueError('pin node mismatch')
  observed[ref]=True;rows.append({'reference':ref,'physicalPinOrder':numbers,'nodes':tokens[1:3]})
 if set(observed)!=set(by_ref):raise ValueError('component coverage mismatch')
 return rows
text=target.read_text(encoding='utf-8');report={'passed':False,'scope':'seven built-in scalar R/C/L/V components and14 physical pins; not CIR/profile/model/solver acceptance','oracleSha256':oracle_hash,'netSha256':before,'cases':[]}
try:
 report['mapping']=compare(text);report['cases'].append({'case':'exact_frozen_dsn_mapping_and_parameters','passed':True})
 variants={'wrong_node':text.replace('N00525 N00509','N00525 0',1),'missing_component':'\n'.join(l for l in text.splitlines() if not l.startswith('L_L1')),'changed_value':text.replace(' 500 TC',' 501 TC',1),'voltage_polarity':text.replace('V_V1         N00525 0','V_V1         0 N00525',1)}
 for name,bad in variants.items():
  assert bad!=text
  try:compare(bad)
  except ValueError as e:report['cases'].append({'case':name,'rejected':str(e),'passed':True})
  else:raise AssertionError('negative accepted')
 report['passed']=True
except Exception as e:report['error']=str(e)
report['originalUnchanged']=sha256(target)==before and sha256(a.oracle)==oracle_hash;report['passed']=report['passed'] and report['originalUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}),flush=True)
