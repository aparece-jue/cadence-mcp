"""Native-service identity acceptance on four exactly overlapping decorative lines."""
import argparse
import json
from pathlib import Path

from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_graphic_line import read_lines
from cadence_mcp.capture_graphic_line_edit import CaptureGraphicLineEdits
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.core import Config,sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('install-root','source','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();source=a.source.resolve(strict=True);before=sha256(source);root=a.output.resolve();root.mkdir(exist_ok=False)
    config=Config(a.install_root,root/'work',(source.parent,root),60);cap=CaptureService(config);writer=CaptureGraphicLineEdits(config,cap)
    report=dict(passed=False,scope='native service, complementary to actual MCP pose/deletion matrix',sourceSha256=before,cases=[])
    plans=[]
    try:
        sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId']
        page,=[p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE']
        rows=query_page_vectors(cap,sid,page['objectId'],limit=1000)['items'];assert len(rows)==4
        assert all(r['kind']=='line' and r['localDescriptor']==['line',[0,0],[100,0],1,1] and r['location']==[500,500] and r['rotationCode']==r['mirrorCode']==0 for r in rows)
        original_ids=[r['nativeId'] for r in rows];assert len(set(original_ids))==4
        colored=read_lines(config,cap.sessions[sid]['design'],root,'HALFADD','MCP_PLACE',True,True,True)
        assert [r['lineColor'] for r in colored]==[1,8,47,48] and [r['definitionColor'] for r in colored]==[1,8,47,48]
        change=dict(localStart=[0,0],localEnd=[100,0],location=[500,500],rotation=0,mirror=0,lineStyle=1,lineWidth=1,lineColor=8)
        plan=writer.plan_edit(sid,rows[2]['objectId'],'update',change);result=writer.apply(plan['planId'],plan['planDigest'],'duplicate-color-only');plans.append((plan,result))
        cap.close(sid);target=config.workspace_root/result['outputWorkspaceRelativePath']/'design.dsn'
        sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];page,=[p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE']
        rows=query_page_vectors(cap,sid,page['objectId'],limit=1000)['items'];assert [r['nativeId'] for r in rows]==original_ids
        colored=read_lines(config,target,root,'HALFADD','MCP_PLACE',True,True,True)
        assert [r['lineColor'] for r in colored]==[1,8,8,48] and [r['definitionColor'] for r in colored]==[1,8,8,48]
        report['cases'].append(dict(operation='color_only_update',targetNativeId=original_ids[2],nativeIds=original_ids,colors=[1,8,8,48],passed=True))
        plan=writer.plan_edit(sid,rows[1]['objectId'],'delete');result=writer.apply(plan['planId'],plan['planDigest'],'duplicate-delete-exact');plans.append((plan,result))
        cap.close(sid);target=config.workspace_root/result['outputWorkspaceRelativePath']/'design.dsn'
        sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];page,=[p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE']
        rows=query_page_vectors(cap,sid,page['objectId'],limit=1000)['items'];expected_ids=[original_ids[i] for i in (0,2,3)]
        assert [r['nativeId'] for r in rows]==expected_ids
        colored=read_lines(config,target,root,'HALFADD','MCP_PLACE',True,True,True)
        assert [r['lineColor'] for r in colored]==[1,8,48] and [r['definitionColor'] for r in colored]==[1,8,48]
        report['cases'].append(dict(operation='delete_one_of_equal_color_twins',targetNativeId=original_ids[1],remainingNativeIds=expected_ids,colors=[1,8,48],passed=True));cap.close(sid)
        fresh=CaptureGraphicLineEdits(config,CaptureService(config))
        for plan,result in plans:
            got=fresh.recover(plan['planId'],plan['planDigest']);assert got['artifact']['sha256']==result['artifact']['sha256']
        report.update(passed=True,freshRecoveryWithoutReplay=True)
    except Exception as error:report.update(error=str(error),errorType=type(error).__name__)
    report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged']
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report));assert report['passed']


if __name__=='__main__':main()
