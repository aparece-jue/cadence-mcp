"""Native reference rename/swap acceptance with explicit physical pin expectations."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import CaptureReferenceEdits
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','unbound-source','connected-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
sources={'unbound':a.unbound_source,'connected':a.connected_source}
cases=[{'name':'rename_unbound','source':'unbound','map':{'R101':'R201'}},
       {'name':'swap_unbound','source':'unbound','map':{'R101':'R102','R102':'R101'}},
       {'name':'rename_connected','source':'connected','map':{'R101':'R201'}},
       {'name':'swap_connected','source':'connected','map':{'R101':'R102','R102':'R101'}}]
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
config=Config(a.install_root,root/'work',tuple({p.parent for p in sources.values()}),60);report={'passed':False,'cases':[]}
for fixture in cases:
    row={'name':fixture['name'],'passed':False};report['cases'].append(row);source=sources[fixture['source']];row['sourceHashBefore']=sha256(source)
    try:
        cap=CaptureService(config);writer=CaptureReferenceEdits(config,cap);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];parts=cap.sessions[sid]['data']['part']
        mappings=[{'partId':next(p['objectId'] for p in parts if p['reference']==old),'newReference':new} for old,new in fixture['map'].items()]
        plan=writer.plan(sid,mappings);row['plan']=plan;result=writer.apply(plan['planId'],plan['planDigest'],fixture['name']);row['result']=result
        fresh=CaptureReferenceEdits(config,CaptureService(config));again=fresh.apply(plan['planId'],plan['planDigest'],fixture['name']);assert again['artifact']['sha256']==result['artifact']['sha256']
        opened=fresh.open_output(plan['planId'],plan['planDigest']);row['opened']=opened
        data=fresh.capture.sessions[opened['sessionId']]['data'];page=next(p for p in data['page'] if p['name']=='MCP_PLACE');observed=[p for p in data['pin'] if p['pageId']==page['objectId']]
        expected=[]
        for old in ('R101','R102'):
            for num in ('1','2'):
                bound=fixture['source']=='connected' and (old,num) in (('R101','2'),('R102','1'))
                expected.append((fixture['map'].get(old,old),num,bound,'MCP_MIDDLE' if bound else ''))
        assert sorted((p['reference'],p['number'],p['connected'],p['net']) for p in observed)==sorted(expected)
        row['sourceHashAfter']=sha256(source);assert row['sourceHashAfter']==row['sourceHashBefore'];row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),errorCode=getattr(error,'code',None))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('name','passed','errorCode','error')}),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
