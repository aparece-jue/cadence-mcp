"""Independent flat-net partition checks on saved owned clone, never saves or repairs."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import run_tcl
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','clone'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60)
expected={'addedContext':'halfadd_C','copyOf':'halfadd_A','occurrences':23,'pinCountRationale':'two inverter units with input/output/VCC/GND =8 plus four two-input gate units with three signals/VCC/GND =20; total28','pinCountsByContext':{'halfadd_A':28,'halfadd_B':28,'halfadd_C':28},'rule':'new nonglobal child networks share no original-context flat objects; original partition retained; C internal pin partition matches A; VCC/GND global merge only'}
write_json(root/'expected.json',expected);report={'passed':False,'scope':'specific saved FULLADD cloned-child flat-net partition acceptance','hashesBefore':{k:sha256(getattr(a,k)) for k in ('source','clone')}}
def read(src,name):
 out=root/(name+'.json');run_tcl(cfg,'inspect_occurrence_nets.tcl',[str(src.resolve(strict=True)),str(out)],root);return json.loads(out.read_text(encoding='utf-8'))
def key(p):return (tuple(p['instancePathSegments']),p['name'],p['occurrencePhysicalNumber'])
def partition(pins):
 groups={};unbound=[]
 for p in pins:
  if p['flatNetId'] is None:unbound.append(key(p))
  else:groups.setdefault(p['flatNetId'],[]).append(key(p))
 return sorted([sorted(g,key=str) for g in groups.values()],key=str),sorted(unbound,key=str)
try:
 before=read(a.source,'before');after=read(a.clone,'after')
 old=[p for p in after['pins'] if p['instancePathSegments'][0]!='halfadd_C']
 assert partition(old)==partition(before['pins']),'original partition changed'
 clone=[p for p in after['pins'] if len(p['instancePathSegments'])==2 and p['instancePathSegments'][0]=='halfadd_C']
 original=[p for p in after['pins'] if len(p['instancePathSegments'])==2 and p['instancePathSegments'][0]=='halfadd_A']
 report['observedChildPinCounts']={context:len([p for p in after['pins'] if len(p['instancePathSegments'])==2 and p['instancePathSegments'][0]==context]) for context in expected['pinCountsByContext']}
 assert report['observedChildPinCounts']==expected['pinCountsByContext'],'declared child pin counts differ'
 def normalize(rows):
  return [{**p,'instancePathSegments':['CHILD',*p['instancePathSegments'][1:]]} for p in rows]
 assert partition(normalize(clone))==partition(normalize(original)),'cloned internal partition differs'
 old_ids={p['flatNetId'] for p in old if p['flatNetId'] is not None}
 shared=[]
 for pin in clone:
  if pin['flatNetId'] in old_ids:
   assert pin['isGlobal'] and pin['flatNetName'] in ('VCC','GND'),'new private net merged with old context'
   shared.append({'pin':key(pin),'name':pin['flatNetName']})
 report.update(passed=True,checks={'originalPartition':True,'clonedChildPartition':True,'privateIsolation':True,'onlyVccGndShared':True},shared=shared)
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 report['hashesAfter']={k:sha256(getattr(a,k)) for k in ('source','clone')};report['passed'] &= report['hashesBefore']==report['hashesAfter']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
