"""Wrong explicit clone hotspot must fail after native save, with no replay."""
import argparse,json
from pathlib import Path
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_hierarchy_edit import CaptureHierarchyEdits
from cadence_mcp.core import Config,CadenceError,sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','oracle'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.source.parent,),60)
report={'passed':False,'sourceBefore':sha256(a.source)}
try:
 cap=CaptureService(cfg);ws=cap.create_workspace(str(a.source));sid=cap.open(ws['workspaceId'])['sessionId'];part=next(p for p in cap.sessions[sid]['data']['part'] if p['reference']=='halfadd_A')
 pins=[{k:p[k] for k in ('name','number','hotSpot')} for p in json.loads(a.oracle.read_text())['geometry']['pins']];pins[0]['hotSpot'][0]+=1
 writer=CaptureHierarchyEdits(cfg,cap);plan=writer.plan(sid,part['objectId'],'halfadd_NEG',[2000,2000],pins);report['plan']=plan
 try:writer.apply(plan['planId'],plan['planDigest'],'wrong-hotspot')
 except CadenceError as e:assert e.code=='hierarchy_geometry_mismatch',e.code;report['errorCode']=e.code
 else:raise AssertionError('Wrong caller hotspot was accepted')
 d=writer.root/('plan-'+plan['planId']);before=sha256(d/'design.dsn');ledger=json.loads((d/'plan.json').read_text());report['process']=ledger['process'];assert ledger['state']=='failed' and ledger['process']['returnCode']==0 and ledger['process']['remainingOwnedProcesses']==0
 assert json.loads((d/'native-result.json').read_text())['saved']
 fresh=CaptureHierarchyEdits(cfg,CaptureService(cfg))
 for action,wanted in [(lambda:fresh.apply(plan['planId'],plan['planDigest'],'wrong-hotspot'),'write_not_replayed'),(lambda:fresh.open_output(plan['planId'],plan['planDigest']),'output_unverified'),(lambda:fresh.recover(plan['planId'],plan['planDigest']),'hierarchy_geometry_mismatch')]:
  try:action()
  except CadenceError as e:assert e.code==wanted,e.code
  else:raise AssertionError('Expected failed-state guard did not reject')
 report['outputUnchanged']=before==sha256(d/'design.dsn');report['passed']=report['outputUnchanged']
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceBefore']==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
