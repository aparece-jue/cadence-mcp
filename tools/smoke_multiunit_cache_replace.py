"""Original homogeneous/heterogeneous group oracles applied to compatible cache replacement; failures retained."""
import argparse,json,copy,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_cache_replace import CaptureCacheReplacements
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','placement-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);prior=json.loads((a.placement_root/'report.json').read_text(encoding='utf-8'));assert prior['passed'];report={'passed':False,'cases':[]}
for old in prior['cases']:
 row={'case':old['case'],'passed':False};report['cases'].append(row)
 try:
  source_dir=a.placement_root/'work'/old['result']['outputWorkspaceRelativePath'];source=source_dir/'design.dsn';library_path=source_dir/'library.olb'
  assert sha256(source)==old['result']['artifact']['sha256'];before={'design':sha256(source),'library':sha256(library_path)}
  c=Config(a.install_root,root/old['case'],(source_dir,),60);cap=CaptureService(c);lib=LibraryService(c);writer=CaptureCacheReplacements(c,cap,lib)
  sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];lid=lib.open(str(library_path))['libraryId'];ld=lib.sessions[lid]['data'];pkg=next(p for p in ld['package'] if p['name']==old['plan']['preview']['packageName']);units=read_units(cap,sid)
  declarations=[]
  for declaration in old['plan']['preview']['units']:
   unit=next(u for u in units.values() if u['reference']=='U501' and u['deviceDesignator']==declaration['deviceDesignator'])
   device=next(d for d in ld['device'] if d['packageId']==pkg['objectId'] and d['designator']==declaration['deviceDesignator'])
   part=next(p for p in ld['part'] if p['deviceId']==device['objectId'] and p['name']==declaration['partName'])
   declarations.append({'partId':unit['partId'],'libraryPartId':part['objectId'],'pins':copy.deepcopy(declaration['expectedPins'])})
  (root/(old['case']+'-declarations.json')).write_text(json.dumps(declarations,indent=2),encoding='utf-8')
  plan=writer.plan(sid,declarations[0]['partId'],lid,pkg['objectId'],declarations);row['plan']=plan
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  result=writer.apply(plan['planId'],plan['planDigest'],'multiunit');row['result']=result;assert result['changedInstanceCount']==len(declarations)
  output=writer.open_output(plan['planId'],plan['planDigest']);row['opened']=output
  row['sourceHashesBefore']=before;row['sourceHashesAfter']={'design':sha256(source),'library':sha256(library_path)};assert row['sourceHashesBefore']==row['sourceHashesAfter'];row['passed']=True
 except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('case','passed','error')}),flush=True)
report['passed']=all(row['passed'] for row in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
