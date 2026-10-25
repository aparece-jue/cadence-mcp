import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();source=a.source.resolve();root.mkdir(exist_ok=False);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashBefore':sha256(source)}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    response=await client.call_tool(name,args);assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in parts if p['reference']=='halfadd_A');before=await call('capture_get_display_font',{'sessionId':sid,'partId':target['objectId'],'property':'Reference'});report['before']=before;assert before['fontDefault'] is True
   request={**before['font'],'height':-19,'weight':600,'quality':1};report['declared']=request;plan=await call('capture_plan_display_font',{'sessionId':sid,'partId':target['objectId'],'property':'Reference','font':request});report['plan']=plan;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');key={k:plan[k] for k in ('planId','planDigest')};await call('capture_close',{'sessionId':sid});result=await call('capture_apply_display_font',{**key,'idempotencyKey':'default-font'});report['result']=result;sid=(await call('capture_open_edit_result',{**key,'kind':'display_font'}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in parts if p['reference']=='halfadd_A');after=await call('capture_get_display_font',{'sessionId':sid,'partId':target['objectId'],'property':'Reference'});report['after']=after;assert after['fontDefault'] is False and after['font']==request;await call('capture_close',{'sessionId':sid});report['passed']=True
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
