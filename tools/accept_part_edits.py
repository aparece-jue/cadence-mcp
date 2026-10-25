"""Native acceptance for fixed definition-level move/delete cases."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_part_edit import CapturePartEdits
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','unbound-source','connected-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cases=[{'name':'move_unbound','source':'unbound','operation':'set_pose','location':[350,400],
        'pins':[{'number':'1','name':'1','hotSpot':[340,410]},{'number':'2','name':'2','hotSpot':[380,410]}]},
       {'name':'delete_unbound','source':'unbound','operation':'delete'},
       {'name':'move_connected','source':'connected','operation':'set_pose','location':[300,500],
        'pins':[{'number':'1','name':'1','hotSpot':[290,510]},{'number':'2','name':'2','hotSpot':[330,510]}]},
       {'name':'delete_connected','source':'connected','operation':'delete'},
       {'name':'wrong_hotspot','source':'unbound','operation':'set_pose','location':[350,400],
        'pins':[{'number':'1','name':'1','hotSpot':[341,410]},{'number':'2','name':'2','hotSpot':[380,410]}],'expectedError':'part_edit_geometry_mismatch'}]
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
sources={'unbound':a.unbound_source,'connected':a.connected_source}
config=Config(a.install_root,root/'work',tuple({p.parent for p in sources.values()}),60)
report={'passed':False,'cases':[]}
for fixture in cases:
    row={'name':fixture['name'],'passed':False};report['cases'].append(row)
    source=sources[fixture['source']];row['sourceHashBefore']=sha256(source)
    try:
        cap=CaptureService(config);writer=CapturePartEdits(config,cap)
        ws=cap.create_workspace(str(source));opened=cap.open(ws['workspaceId']);sid=opened['sessionId'];data=cap.sessions[sid]['data']
        part=next(p for p in data['part'] if p['reference']=='R101')
        page=next(p for p in data['page'] if p['objectId']==part['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==part['schematicId'])
        refs=['R102'] if fixture['operation']=='delete' else ['R101','R102']
        expectations=[]
        for ref in refs:
            for number in ('1','2'):
                bound=fixture['source']=='connected' and ref=='R102' and number=='1'
                expectations.append({'schematicName':sch['name'],'pageName':page['name'],'reference':ref,'pinNumber':number,'connected':bound,'net':'MCP_MIDDLE' if bound else None})
        params={} if fixture['operation']=='delete' else {'location':fixture['location'],'rotation':0,'mirror':0,'expected_pins':fixture['pins']}
        plan=writer.plan(sid,part['objectId'],fixture['operation'],expectations,**params);row['plan']=plan
        try:result=writer.apply(plan['planId'],plan['planDigest'],fixture['name'])
        except CadenceError as error:
            assert error.code==fixture.get('expectedError'),(error.code,str(error))
            row['expectedError']=error.code
            try:writer.apply(plan['planId'],plan['planDigest'],fixture['name'])
            except CadenceError as replay:assert replay.code=='write_not_replayed'
            else:raise AssertionError('Rejected artifact was replayed')
        else:
            assert 'expectedError' not in fixture
            row['result']=result
            replay=CapturePartEdits(config,CaptureService(config))
            assert replay.apply(plan['planId'],plan['planDigest'],fixture['name'])['artifact']['sha256']==result['artifact']['sha256']
            output=replay.open_output(plan['planId'],plan['planDigest']);row['opened']=output
            assert result['pageGeometryVerified'] and result['expectedDefinitionsVerified']
            assert output['counts']['part']==opened['counts']['part']-(fixture['operation']=='delete')
        row['sourceHashAfter']=sha256(source);assert row['sourceHashAfter']==row['sourceHashBefore'];row['passed']=True
    except BaseException as error:
        row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'name':row['name'],'passed':row['passed'],'error':row.get('error')}),flush=True)
report['passed']=all(c['passed'] for c in report['cases'])
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
