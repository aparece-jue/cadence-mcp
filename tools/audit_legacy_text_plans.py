"""Read-only verification of pre-update durable text-add payloads; no native mutation replay."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_graphic_text import CaptureGraphicTexts
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','old-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);old=a.old_root.resolve();report_path=old/'report.json';oldreport=json.loads(report_path.read_text(encoding='utf-8'));assert oldreport['passed'] and oldreport['tools']==199;cfg=Config(a.install_root,root.parent,(old,),60);writer=CaptureGraphicTexts(cfg,CaptureService(cfg));report={'passed':False,'oldReportSha256':sha256(report_path),'cases':[]}
for i,case in enumerate(oldreport['cases']):
 plan_id=case['plan']['planId'];d=old/'work/isolated-jobs/capture_graphic_text'/('plan-'+plan_id);ledger=d/'plan.json';row=json.loads(ledger.read_text(encoding='utf-8'));assert row['state']=='verified' and 'operation' not in row['plan']['payload'];before={n:sha256(d/n) for n in ('design.dsn','native-result.json','plan.json')};target=root/('plan-'+plan_id);target.mkdir()
 for name in ('design.dsn','native-result.json'):shutil.copy2(d/name,target/name)
 result=writer.verify(target,row['plan']['payload'],True);assert result['pageAnchorVerified'] and result['modeledGraphicsAndInstancesPreserved'] and not result['graphicRemovalVerified'];assert sha256(target/'design.dsn')==before['design.dsn'];assert all(sha256(d/name)==v for name,v in before.items());report['cases'].append({'case':i,'passed':True,'originalSha256':before,'newMutationExecuted':False});print(json.dumps({'case':i,'passed':True}),flush=True)
report['passed']=len(report['cases'])==3 and sha256(report_path)==report['oldReportSha256'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
