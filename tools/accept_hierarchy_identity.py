"""Native occurrence identity acceptance; reads only registered design copies."""
import argparse
import json
from pathlib import Path
from cadence_mcp.core import Config, CadenceError, sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_hierarchy import get_hierarchy

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args(); root=a.workspace_root.resolve(); root.mkdir(exist_ok=False)
expected={'': ['halfadd_A','halfadd_B','U1A'],
          'halfadd_A':['U3A','U2A','U3B','U2B','U2C','U1B'],
          'halfadd_B':['U3C','U2D','U3D','U4A','U4B','U1C']}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
report={'passed':False,'checks':{},'sourceHashBefore':sha256(a.source)}
def refused(code, function):
    try: function()
    except CadenceError as e:
        assert e.code==code,(e.code,code)
    else: raise AssertionError('Expected rejection: '+code)
try:
    assert report['sourceHashBefore']=='27c6d11ffbb8d677954d8e56eba26a4b725c677aa83a08020da682972e1ef104'
    cap=CaptureService(Config(a.install_root,root/'work',(a.source.parent,),60))
    ws=cap.create_workspace(str(a.source)); opened=cap.open(ws['workspaceId']); sid=opened['sessionId']
    first=get_hierarchy(cap,sid,None,3); items=first['items']; cursor=first['nextCursor']
    refused('stale_cursor',lambda:get_hierarchy(cap,sid,cursor,4))
    while cursor:
        page=get_hierarchy(cap,sid,cursor,3)
        assert page['total']==16 and page['revision']==opened['revision']
        items+=page['items']; cursor=page['nextCursor']
    assert len(items)==16 and len({x['occurrenceId'] for x in items})==16
    assert [x['depth'] for x in items].count(0)==1
    by_id={x['occurrenceId']:x for x in items}
    actual={key:[] for key in expected}
    for row in items:
        parent=row['parentId']
        if parent is None:
            assert row['instancePathSegments']==[]
            continue
        context=by_id[parent]['reference']
        actual[context].append(row['reference'])
        assert row['instancePathSegments']==by_id[parent]['instancePathSegments']+[row['reference']]
    assert {k:sorted(v) for k,v in actual.items()}=={k:sorted(v) for k,v in expected.items()},actual
    assert len({tuple(x['instancePathSegments']) for x in items})==16
    assert len({x['path'] for x in items})<16
    assert get_hierarchy(cap,sid,None,1000)['items']==items
    second=cap.open(ws['workspaceId'])
    refused('stale_cursor',lambda:get_hierarchy(cap,second['sessionId'],first['nextCursor'],3))
    again=get_hierarchy(cap,second['sessionId'],None,1000)
    assert again['items']==items
    assert not first['occurrenceConnectivityVerified']
    cap.close(sid)
    refused('session_lost',lambda:get_hierarchy(cap,sid,None,3))
    report.update(passed=True,items=items,checks={'declared_tree':True,'multiunit_identity':True,
        'repeated_raw_paths_preserved':True,'paging_and_repeat':True,'cursor_session_and_limit_binding':True,
        'independent_native_reopen':True,'close_rejection':True})
except BaseException as error:
    report.update(errorType=type(error).__name__,error=str(error))
finally:
    report['sourceHashAfter']=sha256(a.source)
    if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='items'},ensure_ascii=False))
raise SystemExit(0 if report['passed'] else 1)
