"""Prepare approved property edits on an owned multiunit source, preserving old oracles."""
import copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import CapturePropertyEdits
r=Path(__file__).resolve().parents[1];root=r/'.local/crosspage-overrides-source-20261029';root.mkdir(exist_ok=False)
case=copy.deepcopy(next(x for x in json.loads((r/'.local/crosspage-cached-unit-native-20261025/expected.json').read_text(encoding='utf-8')) if x['case']=='B-cross'));source=Path(case['source']);before=sha256(source);assert before==case['sourceBefore']
overrides={'Value':'USER OVERRIDE 00123 Ω','PCB Footprint':'CUSTOM_00123'};(root/'oracle.json').write_text(json.dumps({'overrides':overrides,'sourceBefore':before,'pins':case['expectedPins']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
cap=CaptureService(Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),60));edits=CapturePropertyEdits(cap.config,cap);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];results=[]
for key,value in overrides.items():
 part=next(p for p in cap.sessions[sid]['data']['part'] if p['reference']=='U501');plan=edits.plan(sid,part['objectId'],key,value);result=edits.apply(plan['planId'],plan['planDigest'],'override-'+key);results.append(result);opened=edits.open_output(plan['planId'],plan['planDigest']);cap.close(sid);sid=opened['sessionId']
target=root/'source.dsn';shutil.copy2(cap.sessions[sid]['design'],target);cap.close(sid);assert sha256(source)==before
case.update(source=str(target),sourceBefore=sha256(target),overrides=overrides);(root/'expected.json').write_text(json.dumps([case],ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(root/'report.json').write_text(json.dumps({'passed':True,'sourceUnchanged':True,'overrides':overrides,'results':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Private override source prepared by verified property tasks.',flush=True)
