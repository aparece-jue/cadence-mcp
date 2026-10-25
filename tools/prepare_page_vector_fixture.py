import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
import argparse
p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();source=a.source.resolve();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);target=root/'design.dsn';shutil.copy2(source,target);c=Config(a.install_root.resolve(),root/'work',(root,source.parent),60)
expected=[]
for rotation in range(4):
 for i,kind in enumerate(('line','box','ellipse','arc','polygon','polyline','bezier','text')):
  v={'line':['line',[-10,5],[50,35],2,1],'box':['box',[-10,-20,50,40],2,1,1,0],'ellipse':['ellipse',[-10,-20,50,40],2,1,1,0],'arc':['arc',[-10,-20,50,40],[50,10],[20,-20],2,1],'polygon':['polygon',[[-10,5],[10,-15],[30,35],[50,5]],2,1,1,0],'polyline':['polyline',[[-10,5],[10,-15],[30,35],[50,5]],2,1],'bezier':['bezier',[[-10,5],[10,-15],[30,35],[50,5]],2,1]}.get(kind)
  if kind=='text':v=['text','中文 [x]$;\nR1 / R10',[-10,-20],[-10,-20,50,40],['Arial',-11,0,0,0,700,1,0,0,0,7,0,1,16],0]
  expected.append({'kind':kind,'location':[200+150*i,1000+200*rotation],'rotationCode':rotation,'mirrorCode':rotation%2,'localDescriptor':v})
(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8');report={'passed':False,'sourceHashBefore':sha256(source),'expectedHashBefore':sha256(root/'expected.json')}
try:
 cap=CaptureService(c);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];baseline=definition_baseline(cap.sessions[sid]['data']);cap.close(sid)
 process=run_owned_process([c.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_page_vectors.tcl'),c.install_root,target,root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(c),60);report['process']=process;report['receipt']=json.loads((root/'receipt.json').read_text(encoding='utf-8'));assert process['returnCode']==0,report['receipt']
 sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];assert definition_baseline(cap.sessions[sid]['data'])==baseline
 page=next(p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE');actual=query_page_vectors(cap,sid,page['objectId'],limit=1000);report['query']=actual;assert actual['total']==32 and actual['supportedGeometryComplete'];differences=[]
 for wanted,row in zip(expected,actual['items']):
  diff={k:{'expected':v,'actual':row[k]} for k,v in wanted.items() if row[k]!=v}
  if diff:differences.append({'kind':wanted['kind'],'rotationCode':wanted['rotationCode'],'differences':diff})
 report['differences']=differences;report['passed']=not differences;cap.close(sid)
except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
report['sourceHashAfter']=sha256(source);report['expectedHashAfter']=sha256(root/'expected.json');report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['expectedHashBefore']==report['expectedHashAfter'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error'),'differences':report.get('differences')},ensure_ascii=False));raise SystemExit(0 if report['passed'] else 1)
