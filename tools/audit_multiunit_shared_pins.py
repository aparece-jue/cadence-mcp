"""Read-only documented bReturnShared=1 audit of frozen failed placement outputs."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_edit import definition_baseline
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','previous-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);previous=a.previous_root.resolve(strict=True);source=a.source.resolve(strict=True);cfg=Config(a.install_root,root,(root,),60);original=previous/'report.json';oldhash=sha256(original);report={'passed':False,'originalReportSha256':oldhash,'scope':'bReturnShared1 read-only audit, no write ledger promotion or native mutation','cases':[]}
def inspect(name,path,d,label,extra):
 original_script=(ADAPTERS/name).read_text(encoding='utf-8');s=original_script.replace('NewPinsIter $state]', 'NewPinsIter $state $::IterDefs_ALL 1]');s=s.replace('[file join [file dirname [info script]] json.tcl]','{'+str(ADAPTERS/'json.tcl').replace('\\','/')+'}').replace('[file join [file dirname [info script]] dbo_pin_net.tcl]','{'+str(ADAPTERS/'dbo_pin_net.tcl').replace('\\','/')+'}')
 script=d/(label+'.tcl');script.write_text(s,encoding='utf-8');out=d/(label+'.json');process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(script),str(cfg.install_root),str(path),str(out),*extra],d,process_env(cfg),60)
 if process['returnCode']!=0:raise RuntimeError('Shared reader failed '+name)
 assert process['remainingOwnedProcesses']==0
 return json.loads(out.read_text())
source_before=sha256(source);baseline=inspect('inspect.tcl',source,root,'source-shared',['100000']);report['sourceSharedPinRows']=len(baseline['pin'])
for name in ('shared_dual-unbound','shared_dual-power-wire'):
 d=root/name;d.mkdir();target=previous/name/'design.dsn';before=sha256(target);wanted=json.loads((previous/name/'expected.json').read_text());row={'case':name,'passed':False};report['cases'].append(row)
 try:
  data=inspect('inspect.tcl',target,d,'definition-shared',['100000']);selected=[p for p in data['part'] if p['reference']=='U501'];newpins=[p for p in data['pin'] if p['reference']=='U501'];expected={}
  for unit in wanted['units']:
   for pin in unit['pins']:expected[(unit['designator'],pin['number'],pin['name'])]=pin['hotSpot']
  row['newPinRows']=len(newpins);row['sharedPowerRows']=sum(p['number']=='8' and p['name']=='VCC' for p in newpins);row['declaredPinNamesNumbersMatch']=sorted((p['number'],p['name']) for p in newpins)==sorted((key[1],key[2]) for key in expected)
  preserved={k:[p for p in rows if p.get('reference')!='U501'] for k,rows in data.items()};row['allOriginalDefinitionPinsPreserved']=definition_baseline(preserved)==definition_baseline(baseline)
  units=json.loads((previous/name/'units.json').read_text());unit_ids={u['partId']:u['deviceDesignator'] for u in units if u['reference']=='U501'};checks=[]
  for part in selected:
   geom=inspect('inspect_part_geometry.tcl',target,d,'geometry-'+unit_ids[part['objectId']],[part['objectId'],'100000','10000']);checks.append(len(geom['pins'])==3 and all(expected[(unit_ids[part['objectId']],p['number'],p['name'])]==p['hotSpot'] for p in geom['pins']))
  row['declaredSharedHotspotsMatch']=len(checks)==2 and all(checks)
  wired=name.endswith('power-wire');row['declaredNetsMatch']=all(p['connected']==(wired and p['name']=='VCC') and p['net']==('VCC' if wired and p['name']=='VCC' else '') for p in newpins)
  if wired:
   bindings=inspect('inspect_net_symbol_bindings.tcl',target,d,'bindings-shared',[]);power=[p for p in bindings if p['kind']=='pin' and p['reference'] in ('U501A','U501B') and p['number']=='8'];wire=[p for p in bindings if p['kind']=='wire' and p['pageName']=='MCP_PLACE' and any(pt[0]>=1000 for pt in p['points'])];row['nativeSharedPowerGroupMatches']=len(power)==2 and len(wire)==3 and power[0]['group'] is not None and len({p['group'] for p in power+wire})==1
  row['sourceAndOutputUnchanged']=sha256(target)==before and sha256(source)==source_before;row['passed']=all(row[k] for k in ('declaredPinNamesNumbersMatch','allOriginalDefinitionPinsPreserved','declaredSharedHotspotsMatch','declaredNetsMatch','sourceAndOutputUnchanged')) and (not wired or row['nativeSharedPowerGroupMatches'])
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,row,flush=True)
report['originalReportUnchanged']=sha256(original)==oldhash;report['passed']=all(c['passed'] for c in report['cases']) and report['originalReportUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
