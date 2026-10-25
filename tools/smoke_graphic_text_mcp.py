import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument("--expected-tools",type=int,default=200)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source)
cases=[{'rotation':0,'mirror':0,'text':'MCP文本 [x]$;\nR1 / R10','location':[300,450],'font':{}},{'rotation':1,'mirror':1,'text':'旋转 Ω中文','location':[420,520],'font':{'height':-17,'weight':700,'italic':True,'underline':True}},{'rotation':3,'mirror':0,'text':'文字三','location':[500,600],'font':{'faceName':'Courier New','height':-14,'strikeOut':True}}]
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','90'],env=env)
async def main():
 report={'passed':False,'cases':[],'checks':{},'sourceSha256':before,'oracleSha256':oracle}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   async def call(n,args):
    r=await c.call_tool(n,args);assert not r.is_error,(n,r.structured_content);return r.structured_content['data']
   report['tools']=len((await c.list_tools()).tools);assert report['tools']==a.expected_tools
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
   for i,case in enumerate(cases):
    args={'sessionId':sid,'pageId':page['objectId'],'width':180,'height':40,**case};plan=await call('capture_plan_graphic_text_add',args);keys={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_graphic_text_add',{**keys,'idempotencyKey':f'text-{i}'})
    assert result['pageAnchorVerified'] and result['modeledGraphicsAndInstancesPreserved'];opened=await call('capture_open_edit_result',{**keys,'kind':'graphic_text'});pg=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE');rows=(await call('capture_query_page_vectors',{'sessionId':opened['sessionId'],'pageId':pg['objectId'],'limit':1000}))['items'];new=next(v for v in rows if v['kind']=='text' and v['localDescriptor'][1]==case['text']);assert new['pageControlPoints'][0]==case['location'] and new['rotationCode']==case['rotation'] and new['mirrorCode']==case['mirror'];await call('capture_close',{'sessionId':opened['sessionId']});report['cases'].append({'case':case,'plan':plan,'result':result,'observed':new});print(json.dumps({'case':i,'passed':True}),flush=True)
   for change in ({'font':{'quality':2}},{'location':[True,0]},{'pageId':'foreign'},{'text':'a\x00b'},{'width':0}):
    bad=await c.call_tool('capture_plan_graphic_text_add',{'sessionId':sid,'pageId':page['objectId'],'width':180,'height':40,**cases[0],**change});assert bad.is_error
   pending=await call('capture_plan_graphic_text_add',{'sessionId':sid,'pageId':page['objectId'],'width':180,'height':40,**cases[0]});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_graphic_text_add',pk);assert (await c.call_tool('capture_apply_graphic_text_add',{**pk,'idempotencyKey':'cancelled'})).is_error;report['checks']['invalid_and_pending_cancel']=True
   await call('capture_close',{'sessionId':sid})
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   keys={k:report['cases'][0]['plan'][k] for k in ('planId','planDigest')};again=await fresh.call_tool('capture_apply_graphic_text_add',{**keys,'idempotencyKey':'text-0'});assert not again.is_error and again.structured_content['data']['mutationReplayed'] is False
   recovered=await fresh.call_tool('capture_recover_graphic_text_add',keys);assert not recovered.is_error;report['checks']['fresh_apply_recover_no_replay']=True
  report['passed']=True
 except BaseException as e:report['error']=str(e);report['traceback']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')},ensure_ascii=True),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
