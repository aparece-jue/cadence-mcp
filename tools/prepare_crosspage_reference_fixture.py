from pathlib import Path
import copy,json,shutil,traceback
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import CaptureReferenceEdits,read_units
from cadence_mcp.capture_cache_replace import read_state
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
import argparse
p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();prior_root=a.fixture_root.resolve();prior=json.loads((prior_root/'report.json').read_text(encoding='utf-8'))['cases'][0];source=prior_root/'work'/prior['result']['outputWorkspaceRelativePath']/'design.dsn'
root=a.workspace_root.resolve();root.mkdir(exist_ok=False);target=root/'fixture.dsn';shutil.copy2(source,target)
report={'passed':False,'sourceHashBefore':sha256(source),'oracleHashBefore':sha256(prior_root/'report.json')}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
 c=Config(a.install_root.resolve(),root/'work',(root,),60)
 result=run_owned_process([c.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_crosspage_references.tcl'),c.install_root,target,root/'fixture-receipt.json',ADAPTERS/'json.tcl'],root,process_env(c),60)
 report['fixtureProcess']=result;report['fixtureReceipt']=json.loads((root/'fixture-receipt.json').read_text(encoding='utf-8'));dump();assert result['returnCode']==0,report['fixtureReceipt']
 cap=CaptureService(c);writer=CaptureReferenceEdits(c,cap);sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];units=read_units(cap,sid);selected=[u for u in units.values() if u['reference']=='U501'];assert len(selected)==2
 assert {u['pageName'] for u in selected}=={'HALFADD','MCP_PLACE'};assert {u['schematicName'] for u in selected}=={'HALFADD'}
 data=cap.sessions[sid]['data'];state=read_state(c,cap.sessions[sid]['design'],cap.sessions[sid]['design'].parent,units)
 for unit in selected:
  declared=next(u for u in prior['plan']['preview']['units'] if u['deviceDesignator']==unit['deviceDesignator'])
  actual=sorted((p['number'],p['name'],p['connected'],p['net'] if p['connected'] else None) for p in data['pin'] if p['partId']==unit['partId']);expected=sorted((p['number'],p['name'],p['connected'],p['net']) for p in declared['expectedPins']);assert actual==expected
  row=next(s for s in state if s['nativeId']==unit['nativeId']);note=f"位号 U501 / U501{unit['deviceDesignator']} / U5010 [x]$;"
  assert next(p['value'] for p in row['user'] if p['name']=='MCP_NOTE')==note
  for name,location,rotation,display_type in [('Part Reference',[17,23],2,1),('Reference',[19,31],1,2),('MCP_NOTE',[29,37],3,1)]:
   display=next(p for p in row['display'] if p['name']==name);assert display['location']==location and display['rotationCode']==rotation and display['displayTypeCode']==display_type and display['colorCode']==3
 report['fixtureBaseline']=state;report['fixtureHashBefore']=sha256(target);dump()
 owner=next(u for u in selected if u['deviceDesignator']=='B');plan=writer.plan_packages(sid,[{'partId':owner['partId'],'newReference':'U601'}]);report['plan']=plan;dump()
 result=writer.apply(plan['planId'],plan['planDigest'],'crosspage-display');report['result']=result;dump();assert result['modeledAllInstanceStateVerified'] and result['oldNewNodeTableVerified']
 report['fixtureHashAfter']=sha256(target);assert report['fixtureHashAfter']==report['fixtureHashBefore'];report['passed']=True
except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
report['sourceHashAfter']=sha256(source);report['oracleHashAfter']=sha256(prior_root/'report.json');report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['oracleHashBefore']==report['oracleHashAfter'];dump();print(json.dumps({'passed':report['passed'],'error':report.get('error')},ensure_ascii=False));raise SystemExit(0 if report['passed'] else 1)
