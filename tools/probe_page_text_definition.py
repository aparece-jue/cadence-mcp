"""Predeclared text definition coordinate test; never rewrite the old instance-location oracle."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.capture_wire import inventory,connection_digest
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();cfg=Config(a.install_root,root/'work',(root,source.parent),60)
font=['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16];text='MCP88 中文 [x]$;\nR101 / R102';cases=[]
for mirror in (0,1):
 for rotation in range(4):
  x,y=300,450
  for _ in range(rotation):x,y=-y,x
  if mirror:x=-x
  rect=[x,y,x+180,y+40];points=[[x,y],[x,y],[x+180,y],[x+180,y+40],[x,y+40]];world=[]
  for px,py in points:
   if mirror:px=-px
   for _ in range(rotation):px,py=py,-px
   world.append([px,py])
  cases.append({'rotation':rotation,'mirror':mirror,'rawLocation':[x,y],'rawBounds':rect,'expected':{'kind':'text','location':[0,0],'rotationCode':rotation,'mirrorCode':mirror,'localDescriptor':['text',text,[x,y],rect,font,0],'pageControlPoints':world}})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');report={'passed':False,'sourceHash':sha256(source),'oracleHash':oracle,'cases':[]}
def snapshot(path):
 cap=CaptureService(cfg);sid=cap.open(cap.create_workspace(str(path))['workspaceId'])['sessionId']
 try:
  data=cap.sessions[sid]['data'];page=next(p for p in data['page'] if p['name']=='MCP_PLACE');return definition_baseline(data),connection_digest(data,inventory(cap,sid)),query_page_vectors(cap,sid,page['objectId'],limit=1000)['items']
 finally:cap.close(sid)
before=snapshot(source)
for case in cases:
 tag=f"r{case['rotation']}-m{case['mirror']}";d=root/tag;d.mkdir();target=d/'design.dsn';shutil.copy2(source,target);row={'case':tag,'passed':False};report['cases'].append(row)
 try:
  x,y=case['rawLocation'];proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'fixture_page_text_definition.tcl',cfg.install_root,target,d/'receipt.json','HALFADD','MCP_PLACE',str(x),str(y),'180','40',text,'add',str(case['rotation']),str(case['mirror'])],d,process_env(cfg),60);row['process']=proc;row['receipt']=json.loads((d/'receipt.json').read_text(encoding='utf-8'));assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0 and row['receipt']['saved']
  after=snapshot(target);assert before[:2]==after[:2];added=[v for v in after[2] if v['kind']=='text' and v['localDescriptor'][1]==text];assert len(added)==1
  actual={k:added[0][k] for k in case['expected']};row['actual']=actual;row['differences']={k:{'expected':v,'actual':actual[k]} for k,v in case['expected'].items() if v!=actual[k]};row['passed']=not row['differences']
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'case':tag,'passed':row['passed'],'differences':row.get('differences'),'error':row.get('error')},ensure_ascii=True),flush=True)
report['sourceUnchanged']=sha256(source)==report['sourceHash'];report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=all(c['passed'] for c in report['cases']) and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
