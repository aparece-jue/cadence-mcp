"""Native new DSN declaration acceptance and independent metadata observation."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_design_create import CaptureDesignCreates,read_document_meta
from cadence_mcp.capture_pages import CapturePages
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','reference-design'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--ascii-only',action='store_true')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
config=Config(a.install_root,root/'work',(root,),60);cap=CaptureService(config);writer=CaptureDesignCreates(config,cap)
cases=[{'rootName':'ROOT','pageName':'PAGE_ONE'},{'rootName':'根图一','pageName':'电源页'}]
if a.ascii_only:cases=[{'rootName':'ROOT','pageName':'PAGE_ONE'},{'rootName':'POWER_CORE','pageName':'POWER_PAGE'}]
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
report={'passed':False,'cases':[],'referenceHashBefore':sha256(a.reference_design)}
for spec in cases:
    row={'spec':spec,'passed':False};report['cases'].append(row)
    try:
        plan=writer.plan(spec['rootName'],spec['pageName']);row['plan']=plan
        result=writer.apply(plan['planId'],plan['planDigest'],'create-'+spec['rootName']);row['result']=result
        opened=writer.open_output(plan['planId'],plan['planDigest']);row['opened']=opened
        assert opened['counts']=={'schematic':1,'page':1,'part':0,'pin':0}
        if spec['rootName']=='ROOT':
            pages=CapturePages(config,cap);sid=opened['sessionId'];sch=cap.sessions[sid]['data']['schematic'][0]
            edit=pages.plan(sid,'create',sch['objectId'],None,'SECOND_PAGE');out=pages.apply(edit['planId'],edit['planDigest'],'new-design-page')
            row['pagePlan']=edit;row['pageResult']=out
            reopened=pages.open_output(edit['planId'],edit['planDigest']);assert reopened['counts']=={'schematic':1,'page':2,'part':0,'pin':0}
        fresh=CaptureDesignCreates(config,CaptureService(config));again=fresh.apply(plan['planId'],plan['planDigest'],'create-'+spec['rootName'])
        assert again['artifact']['sha256']==result['artifact']['sha256'];row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),errorCode=getattr(error,'code',None))
    print(json.dumps({'spec':spec,'passed':row['passed'],'error':row.get('error')},ensure_ascii=False),flush=True)
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    report['referenceMeta']=read_document_meta(config,a.reference_design,root)
except BaseException as error:report['metaError']=str(error)
report['referenceHashAfter']=sha256(a.reference_design)
report['passed']=all(c['passed'] for c in report['cases']) and 'metaError' not in report and report['referenceHashBefore']==report['referenceHashAfter']
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
