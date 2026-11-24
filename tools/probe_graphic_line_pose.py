"""Private all-pose line update/delete probe before exposing a new writer."""
import argparse
import copy
import json
import shutil
from pathlib import Path

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_graphic_text import graphic_state
from cadence_mcp.capture_graphic_line import read_lines, line_key
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.capture_wire import connection_digest, inventory
from cadence_mcp.core import Config, sha256
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process


def rows(capture, sid):
    page, = [p for p in capture.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE']
    return page, query_page_vectors(capture,sid,page['objectId'],limit=1000)['items']


def plain(row):
    return {k:copy.deepcopy(v) for k,v in row.items() if k not in ('objectId','pageId','index')}


def transform(p,r,m):
    x,y=p
    if m:x=-x
    x,y=[(x,y),(y,-x),(-x,-y),(-y,x)][r]
    return [700+x,800+y]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','install-root','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();source=a.source.resolve(strict=True);before=sha256(source);root=a.output.resolve();root.mkdir(exist_ok=False)
    cfg=Config(a.install_root,root/'work',(root,source.parent),60);c=CaptureService(cfg)
    sid=c.open(c.create_workspace(str(source))['workspaceId'])['sessionId'];page,initial=rows(c,sid)
    assert len(initial)==3 and all(v['kind']=='line' for v in initial)
    native_id=initial[0]['nativeId'];baseline=definition_baseline(c.sessions[sid]['data']);connections=connection_digest(c.sessions[sid]['data'],inventory(c,sid))
    graphics=graphic_state(c,sid)
    source_colors=read_lines(cfg,c.sessions[sid]['design'],root,'HALFADD','MCP_PLACE',True,True)
    assert len(source_colors)==3
    expected=[]
    for r in range(4):
        for m in range(2):
            target=plain(initial[0]);target.update(location=[700,800],rotationCode=r,mirrorCode=m,
                localDescriptor=['line',[-20,15],[40,55],3,2],pageControlPoints=[transform(p,r,m) for p in [[-20,15],[40,55]]])
            expected.append(dict(operation='update',rotation=r,mirror=m,target=target))
    expected.append(dict(operation='delete',rotation=0,mirror=0))
    (root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf8');oracle=sha256(root/'expected.json');c.close(sid)
    report=dict(passed=False,sourceSha256=before,oracleSha256=oracle,cases=[])
    for case in expected:
        name=case['operation']+'-'+str(case['rotation'])+'-'+str(case['mirror']);directory=root/name;directory.mkdir();target=directory/'design.dsn';shutil.copyfile(source,target)
        result=dict(case=name,passed=False);report['cases'].append(result)
        try:
            result['process']=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_suffix('.tcl'),a.install_root,target,directory/'native.json',ADAPTERS/'json.tcl',ADAPTERS/'dbo_qualified_page.tcl',str(native_id),str(case['rotation']),str(case['mirror']),case['operation']],directory,process_env(cfg),45)
            result['receipt']=json.loads((directory/'native.json').read_text());assert result['process']['returnCode']==0 and result['process']['remainingOwnedProcesses']==0 and result['receipt']['saved']
            sid=c.open(c.create_workspace(str(target))['workspaceId'])['sessionId'];_,actual=rows(c,sid)
            want=[plain(v) for v in initial]
            if case['operation']=='delete':del want[0]
            else:want[0]=case['target']
            assert [plain(v) for v in actual]==want,dict(expected=want,actual=[plain(v) for v in actual])
            assert definition_baseline(c.sessions[sid]['data'])==baseline
            assert connection_digest(c.sessions[sid]['data'],inventory(c,sid))==connections
            current_graphics=graphic_state(c,sid)
            assert [v for v in current_graphics if v['scope']!=['HALFADD','MCP_PLACE']]==[v for v in graphics if v['scope']!=['HALFADD','MCP_PLACE']]
            colored=read_lines(cfg,target,directory,'HALFADD','MCP_PLACE',True,True)
            want_colors=copy.deepcopy(source_colors[1:])
            if case['operation']=='update':want_colors.insert(0,dict(localStart=[-20,15],localEnd=[40,55],location=[700,800],start=transform([-20,15],case['rotation'],case['mirror']),end=transform([40,55],case['rotation'],case['mirror']),rotationCode=case['rotation'],mirrorCode=case['mirror'],lineStyle=3,lineWidth=2,lineColor=8,definitionColor=8))
            assert sorted(map(line_key,colored))==sorted(map(line_key,want_colors))
            c.close(sid);result['passed']=True
        except Exception as error:result.update(error=str(error),errorType=type(error).__name__)
        report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
        report['passed']=all(v['passed'] for v in report['cases']) and len(report['cases'])==len(expected) and report['sourceAndOracleUnchanged']
        (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(result),flush=True)
    assert report['passed']


if __name__=='__main__':main()
