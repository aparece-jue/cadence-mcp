import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_pages import CapturePages
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);config=Config(a.install_root.resolve(strict=True),root/'work',(source.parent,),60)
cap=CaptureService(config);writer=CapturePages(config,cap);report={'passed':False,'sourceHashBefore':sha256(source),'cases':[]}
def choose(sid,page=None):
    data=cap.sessions[sid]['data'];sch=next(s for s in data['schematic'] if s['name']=='HALFADD')
    old=next((p for p in data['page'] if p['schematicId']==sch['objectId'] and p['name']==page),None)
    return sch['objectId'],None if old is None else old['objectId']
try:
    sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId']
    for operation,old_name,new_name in [('create',None,'MCP_EMPTY_ACCEPT'),('rename','HALFADD','MCP_RENAMED_ACCEPT')]:
        case={'operation':operation,'oldName':old_name,'newName':new_name,'passed':False};report['cases'].append(case)
        try:
            sch,page=choose(sid,old_name);plan=writer.plan(sid,operation,sch,page,new_name);result=writer.apply(plan['planId'],plan['planDigest'],operation+'-'+new_name)
            opened=writer.open_output(plan['planId'],plan['planDigest']);case.update(passed=True,plan=plan,result=result,opened=opened)
            if operation=='create':
                empty_sid=opened['sessionId'];sch,page=choose(empty_sid,new_name)
                rename=writer.plan(empty_sid,'rename',sch,page,'MCP_EMPTY_RENAMED');res=writer.apply(rename['planId'],rename['planDigest'],'rename-empty')
                second=writer.open_output(rename['planId'],rename['planDigest']);report['cases'].append({'operation':'rename_empty','passed':True,'plan':rename,'result':res,'opened':second})
        except BaseException as error:case.update(error=str(error),errorType=type(error).__name__)
    report['passed']=len(report['cases'])==3 and all(c['passed'] for c in report['cases'])
except BaseException as error:report['error']=str(error)
finally:
    report['sourceHashAfter']=sha256(source)
    if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('operation','passed','error')} for c in report['cases']],'report':str(root/'report.json')}))
