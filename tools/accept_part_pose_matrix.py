"""Explicit affine oracle for a centered owned two-pin symbol; do not fit observations."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_part_edit import CapturePartEdits
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cases=[]
for mirror in (0,1):
    for rotation in range(4):
        pins=[]
        for number,name,x in [('1','A',-20),('2','B',20)]:
            x,y=(-x if mirror else x),0
            for _ in range(rotation):x,y=y,-x
            pins.append({'number':number,'name':name,'hotSpot':[700+x,500+y]})
        cases.append({'rotation':rotation,'mirror':mirror,'location':[700,500],'pins':pins})
(root/'expected.json').write_text(json.dumps({'localPins':[['1','A',[-20,0]],['2','B',[20,0]]],'transform':'mirror x then clockwise quarter turns around declared origin','cases':cases},indent=2),encoding='utf-8')
report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[]}
config=Config(a.install_root,root/'work',(a.source.parent,),60)
for expected in cases:
    row={'rotation':expected['rotation'],'mirror':expected['mirror'],'passed':False};report['cases'].append(row)
    try:
        cap=CaptureService(config);writer=CapturePartEdits(config,cap);ws=cap.create_workspace(str(a.source));sid=cap.open(ws['workspaceId'])['sessionId']
        part=next(p for p in cap.sessions[sid]['data']['part'] if p['reference']=='R401')
        connections=[{'schematicName':'HALFADD','pageName':'MCP_EMPTY_ACCEPT','reference':'R401','pinNumber':n,'connected':False,'net':None} for n in ('1','2')]
        plan=writer.plan(sid,part['objectId'],'set_pose',connections,expected['location'],expected['rotation'],expected['mirror'],expected['pins']);row['plan']=plan
        result=writer.apply(plan['planId'],plan['planDigest'],f"matrix-{expected['rotation']}-{expected['mirror']}")
        row.update(passed=True,result=result)
    except BaseException as error:row.update(errorType=type(error).__name__,errorCode=getattr(error,'code',None),error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('rotation','mirror','passed','errorCode')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
