import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_hierarchy import get_hierarchy
from cadence_mcp.capture_occurrence_properties import query_occurrence_properties
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
import argparse
p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();source=a.source.resolve();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);target=root/'design.dsn';shutil.copy2(source,target);c=Config(a.install_root.resolve(),root/'work',(source.parent,root),60);cap=CaptureService(c);report={'passed':False,'sourceHashBefore':sha256(source)}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];get_hierarchy(cap,sid,None,1000);data=cap.sessions[sid]['data'];baseline=definition_baseline(data);a=next(row for row in cap.sessions[sid]['hierarchy'] if row['instancePathSegments']==['halfadd_A','U3A']);before=query_occurrence_properties(cap,sid,a['occurrenceId']);report['before']=before;old_value=next(p['value'] for p in before['definition']['effective'] if p['name']=='Value');cap.close(sid)
 (root/'expected.json').write_text(json.dumps({'A':'A中文[x]$;\nEND','B':'B中文[x]$;\nEND','AValue':'OCC_A_VALUE','BValue':old_value,'definitionTag':'DEF_SHARED'},ensure_ascii=False,indent=2),encoding='utf-8');report['expectedHashBefore']=sha256(root/'expected.json');dump()
 process=run_owned_process([c.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_occurrence_overrides.tcl'),c.install_root,target,root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(c),60);report['process']=process;report['receipt']=json.loads((root/'receipt.json').read_text(encoding='utf-8'));assert process['returnCode']==0,report['receipt']
 sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];get_hierarchy(cap,sid,None,1000);assert definition_baseline(cap.sessions[sid]['data'])==baseline;report['results']=[]
 for label,path in [('A',['halfadd_A','U3A']),('B',['halfadd_B','U3C'])]:
  row=next(row for row in cap.sessions[sid]['hierarchy'] if row['instancePathSegments']==path);result=query_occurrence_properties(cap,sid,row['occurrenceId']);report['results'].append(result);dump();effective={p['name']:p['value'] for p in result['effective']};user={p['name']:p['value'] for p in result['user']};definition={p['name']:p['value'] for p in result['definition']['effective']};assert user['MCP_SCOPE_TAG']==label+'中文[x]$;\nEND' and effective['MCP_SCOPE_TAG']==user['MCP_SCOPE_TAG'];assert definition['MCP_DEF_TAG']=='DEF_SHARED' and effective['MCP_DEF_TAG']=='DEF_SHARED' and 'MCP_SCOPE_TAG' not in definition;assert effective['Value']==('OCC_A_VALUE' if label=='A' else old_value) and definition['Value']==old_value;assert result['definition']['fullReference']=='U3A'
 assert report['results'][0]['definition']['nativeId']==report['results'][1]['definition']['nativeId']
 root_row=next(row for row in cap.sessions[sid]['hierarchy'] if row['parentId'] is None)
 try:query_occurrence_properties(cap,sid,root_row['occurrenceId'])
 except CadenceError as error:assert error.code=='capability_unavailable';report['rootRefusedBeforeUnsafeBinding']=True
 else:raise AssertionError('Root unsafe binding not refused')
 cap.close(sid);report['passed']=True
except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
report['sourceHashAfter']=sha256(source);report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'];
if (root/'expected.json').exists():report['expectedHashAfter']=sha256(root/'expected.json');assert report['expectedHashBefore']==report['expectedHashAfter']
dump();print(json.dumps({'passed':report['passed'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
