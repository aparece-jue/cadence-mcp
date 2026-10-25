"""Native/MCP page units and exact-edge/outside comment-geometry acceptance."""
import argparse,asyncio,json,os,sys,shutil,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();target=root/'design.dsn';shutil.copy2(source,target);cfg=Config(a.install_root,root/'work',(root,source.parent),60)
lines=[[[10,10],[960,710]],[[0,0],[970,720]],[[-1,100],[10,100]],[[960,100],[971,100]],[[100,-1],[100,10]],[[100,710],[100,721]]]
texts=[('EDGE_BOX',950,700,20,20),('OVER_BOX',950,700,21,21),('OUT_ANCHOR',-1,0,20,20)]
points=lines+[[[x,y],[x,y],[x+w,y],[x+w,y+h],[x,y+h]] for text,x,y,w,h in texts]
expected={'mainDocUnits':[970,720],'mainRawSize':[9700,7200],'otherDocUnits':[500,400],'otherRawSize':[12700,10160],'points':points,'marginCases':{}}
for margin in (0,10):
 fs=[]
 for index,ps in enumerate(points):
  for j,(x,y) in enumerate(ps):
   sides=[s for s,test in [('left',x<margin),('top',y<margin),('right',x>970-margin),('bottom',y>720-margin)] if test]
   if sides:fs.append({'index':index,'controlPointIndex':j,'point':[x,y],'sides':sides})
 expected['marginCases'][str(margin)]=fs
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');report={'passed':False,'sourceSha256':sha256(source),'oracleSha256':oracle,'checks':{}}
proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_page_bounds.tcl'),cfg.install_root,target,root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(cfg),60);report['process']=proc
report['lastNativePhase']=(root/'phase.txt').read_text().strip() if (root/'phase.txt').exists() else None
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not (root/'receipt.json').exists():raise RuntimeError(f"native_exit:{proc['returnCode']};phase:{report['lastNativePhase']};no_receipt")
report['receipt']=json.loads((root/'receipt.json').read_text(encoding='utf-8'));assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0 and report['receipt']['saved'];fixture_before=sha256(target)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as c:
   async def call(n,args):
    r=await c.call_tool(n,args);assert not r.is_error,(n,r.structured_content);return r.structured_content['data']
   report['tools']=len((await c.list_tools()).tools);assert report['tools']==202
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(target)}))['workspaceId']}))['sessionId'];pages={p['name']:p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items']}
   for name,raw,doc,metric in [('BOUND_MAIN',[9700,7200],[970,720],0),('BOUND_OTHER',[12700,10160],[500,400],1)]:
    dim=await call('capture_get_page_dimensions',{'sessionId':sid,'pageId':pages[name]['objectId']});report.setdefault('dimensions',{})[name]=dim;assert dim['dimensionsKnown'] and dim['nativeParameters']['size']==raw and dim['nativeParameters']['docUnits']==doc and dim['nativeParameters']['isMetric']==metric
   rows=(await call('capture_query_page_vectors',{'sessionId':sid,'pageId':pages['BOUND_MAIN']['objectId'],'limit':1000}))['items'];assert len(rows)==9 and [r['pageControlPoints'] for r in rows]==points
   for margin in (0,10):
    result=await call('capture_check_page_graphic_bounds',{'sessionId':sid,'pageId':pages['BOUND_MAIN']['objectId'],'margin':margin});report.setdefault('bounds',{})[str(margin)]=result;mapping={r['objectId']:r['index'] for r in rows};actual=[{'index':mapping[f['objectId']],**{k:f[k] for k in ('controlPointIndex','point','sides')}} for f in result['findings']];assert actual==expected['marginCases'][str(margin)] and result['objectsChecked']==9 and result['controlPointsChecked']==27 and result['designPassed'] is None
   other=await call('capture_check_page_graphic_bounds',{'sessionId':sid,'pageId':pages['BOUND_OTHER']['objectId']});assert other['allSupportedControlPointsInBounds'] and other['objectsChecked']==1 and other['controlPointsChecked']==2
   empty=await call('capture_check_page_graphic_bounds',{'sessionId':sid,'pageId':pages['BOUND_EMPTY']['objectId']});assert empty['objectsChecked']==0 and empty['findings']==[]
   zero=await call('capture_get_page_dimensions',{'sessionId':sid,'pageId':pages['BOUND_ZERO']['objectId']});assert not zero['dimensionsKnown'] and zero['fullPageBounds'] is None;bad=await c.call_tool('capture_check_page_graphic_bounds',{'sessionId':sid,'pageId':pages['BOUND_ZERO']['objectId']});assert bad.is_error and bad.structured_content['error']['code']=='page_dimensions_unknown'
   for args in ({'pageId':'foreign'},{'pageId':pages['BOUND_MAIN']['objectId'],'margin':True},{'pageId':pages['BOUND_MAIN']['objectId'],'margin':360}):assert (await c.call_tool('capture_check_page_graphic_bounds',{'sessionId':sid,**args})).is_error
   await call('capture_close',{'sessionId':sid});assert (await c.call_tool('capture_get_page_dimensions',{'sessionId':sid,'pageId':pages['BOUND_MAIN']['objectId']})).is_error;report['checks']['metric_imperial_exact_edges_outside_margin_other_empty_zero_invalid_closed']=True
  report['passed']=True
 except BaseException as e:report['error']=str(e);report['traceback']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==report['sourceSha256'];report['fixtureUnchanged']=sha256(target)==fixture_before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceUnchanged'] and report['fixtureUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=True),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
