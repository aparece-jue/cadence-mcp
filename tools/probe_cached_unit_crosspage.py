import argparse,copy,json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.capture_multiunit_place import CaptureMultiunitPlacements
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_unit_edit import cache_digest
p=argparse.ArgumentParser()
for n in ('repo','install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();r=a.repo.resolve();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cases=[]
for label,prior,oldcase,missing,cross in [('B-cross','.local/unit-edits-mcp-20261024','delete-B','restore-B',True),('P-cross','.local/unit-edits-final-targeted-20261024','delete-power-P','restore-P',True),('B-same','.local/unit-edits-mcp-20261024','delete-B','restore-B',False)]:
 old=json.loads((r/prior/'report.json').read_text(encoding='utf-8'));case=next(c for c in old['cases'] if c['case']==oldcase);source=r/prior/'work'/case['result']['outputWorkspaceRelativePath']/'design.dsn';assert sha256(source)==case['result']['artifact']['sha256'];directory=r/'.local/cached-unit-add-20261024'/missing;req=json.loads((directory/'request.json').read_text(encoding='utf-8'));pins=copy.deepcopy(json.loads((directory/'expected.json').read_text(encoding='utf-8'))['pins'])
 for pin in pins:
  if not pin['connected']:pin['net']=None
  if label=='P-cross' and pin['number']=='7':pin.update(connected=False,net=None)
 cases.append({'case':label,'source':str(source),'sourceBefore':sha256(source),'request':req,'expectedPins':pins,'cross':cross})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json');report={'passed':False,'cases':[]}
for case in cases:
 row={'case':case['case'],'passed':False};report['cases'].append(row);source=Path(case['source']);config=Config(a.install_root.resolve(),root/case['case'],(source.parent,),60);cap=CaptureService(config);writer=CaptureMultiunitPlacements(config,cap,LibraryService(config));sid=None
 try:
  sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];units=read_units(cap,sid);owner=next(u for u in units.values() if u['reference']=='U501' and u['deviceDesignator']=='A');cache_digest(cap,sid);cache=cap.sessions[sid]['cacheDefinitions'];pkg=next(p for p in cache['package'] if p['name']==owner['packageName']);device=next(d for d in cache['device'] if d['packageId']==pkg['objectId'] and d['designator']==case['request']['deviceDesignator']);part=next(p for p in cache['part'] if p['deviceId']==device['objectId'] and p['name']==case['request']['partName']);data=cap.sessions[sid]['data'];ownerpart=next(p for p in data['part'] if p['objectId']==owner['partId']);target=next(p for p in data['page'] if p['schematicId']==ownerpart['schematicId'] and p['name']==('HALFADD' if case['cross'] else owner['pageName']));existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in data['pin'] if p['pageId']==target['objectId']]
  row['plan']=writer.plan_add(sid,owner['partId'],part['objectId'],case['request']['location'],case['request']['rotation'],case['request']['mirror'],case['expectedPins'],existing,target['objectId'] if case['cross'] else None);plan=row['plan'];row['result']=writer.apply(plan['planId'],plan['planDigest'],case['case']);assert row['result']['crossPageUnitAssignmentVerified']==case['cross'];row['passed']=True
 except BaseException as e:row.update(error=str(e),errorCode=getattr(e,'code',None),traceback=traceback.format_exc())
 finally:
  if sid:cap.close(sid)
 row['sourceUnchanged']=sha256(source)==case['sourceBefore'];row['passed']=row['passed'] and row['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('case','passed','errorCode','error')},ensure_ascii=False),flush=True)
report['oracleUnchanged']=expected_hash==sha256(root/'expected.json');report['passed']=all(c['passed'] for c in report['cases']) and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
