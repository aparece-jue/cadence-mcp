import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import read_units
p=argparse.ArgumentParser()
for n in ('install-root','native-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);native=a.native_root.resolve();reportfile=native/'report.json';expectedfile=native/'expected.json';report=json.loads(reportfile.read_text(encoding='utf-8'));failed=next(c for c in report['cases'] if c['case']=='P-cross');assert not failed['passed'];case=next(c for c in json.loads(expectedfile.read_text(encoding='utf-8')) if c['case']=='P-cross');source=Path(case['source']);job=native/'P-cross/isolated-jobs/capture_multiunit_placement'/('plan-'+failed['plan']['planId']);target=job/'design.dsn';files=[reportfile,expectedfile,target,*job.glob('*.json')];before={str(p):sha256(p) for p in files};cap=CaptureService(Config(a.install_root.resolve(),root/'work',(source.parent,target.parent),60))
def inspect(path):
 sid=cap.open(cap.create_workspace(str(path))['workspaceId'])['sessionId']
 try:
  data=cap.sessions[sid]['data'];units=read_units(cap,sid);rows=[]
  for pin in data['pin']:
   u=units[pin['partId']];rows.append({'schematic':u['schematicName'],'page':u['pageName'],'reference':u['referenceDesignator'] or u['reference'],'number':pin['number'],'name':pin['name'],'connected':pin['connected'],'net':pin['net'] or ''})
  return rows
 finally:cap.close(sid)
old=inspect(source);actual=inspect(target);new=[p for p in actual if p['reference']=='U501P'];remaining=[p for p in actual if p['reference']!='U501P'];key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False);old.sort(key=key);remaining.sort(key=key);expected=[{'schematic':'HALFADD','page':'HALFADD','reference':'U501P',**{k:p[k] for k in ('number','name','connected')},'net':p['net'] or ''} for p in case['expectedPins']];actualnew=sorted(new,key=lambda p:p['number']);expected.sort(key=lambda p:p['number']);differences=[{'number':e['number'],'expected':e,'actual':v} for e,v in zip(expected,actualnew) if e!=v]
out={'passed':len(new)==len(expected) and old==remaining and bool(differences) and all(sha256(p)==before[str(p)] for p in files),'fullFeatureAccepted':False,'originalPinsUnchanged':old==remaining,'newPinDifferences':differences,'originalFailureAndOracleHashes':before,'sourceUnchanged':sha256(source)==case['sourceBefore']};out['passed']=out['passed'] and out['sourceUnchanged'];(root/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':out['passed'],'differences':differences},ensure_ascii=False))
if not out['passed']:raise SystemExit(1)
