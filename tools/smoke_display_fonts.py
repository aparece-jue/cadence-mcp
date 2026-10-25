import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();source=a.source.resolve();root.mkdir(exist_ok=False);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashBefore':sha256(source),'cases':[]}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;report['toolCount']=len(tools);schemas={t.name:t.output_schema for t in tools}
   for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items']
   for index,(ref,property,patch) in enumerate([('U501','Part Reference',{'height':-17,'weight':700,'italic':True,'underline':True,'quality':1}),('R101','Value',{'faceName':'Times New Roman','height':-15,'weight':500,'strikeOut':True,'quality':1}),('U501','MCP_NOTE',{'height':-16,'quality':2})]):
    row={'reference':ref,'property':property,'declaredPatch':patch,'passed':False};report['cases'].append(row)
    try:
     part=next(p for p in parts if p['reference']==ref);before=await call('capture_get_display_font',{'sessionId':sid,'partId':part['objectId'],'property':property});row['before']=before;request={**before['font'],**patch};row['declaredFont']=request
     await call('capture_get_display_font',{'sessionId':sid,'partId':part['objectId'],'property':'MISSING_FONT_PROP'},'display_property_not_found')
     plan=await call('capture_plan_display_font',{'sessionId':sid,'partId':part['objectId'],'property':property,'font':request});row['plan']=plan;dump();key={k:plan[k] for k in ('planId','planDigest')}
     result=await call('capture_apply_display_font',{**key,'idempotencyKey':f'font-{index}'});row['result']=result
     output=(await call('capture_open_edit_result',{**key,'kind':'display_font'}))['sessionId'];outparts=(await call('capture_query',{'sessionId':output,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in outparts if p['objectId']==part['objectId']);actual=await call('capture_get_display_font',{'sessionId':output,'partId':target['objectId'],'property':property});row['after']=actual;assert actual['font']==request and actual['fontDefault'] is False
     assert result['allDisplayFontsVerified'] and result['modeledAllInstanceStateVerified'];await call('capture_close',{'sessionId':output});row['passed']=True
    except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
    dump();print(json.dumps({'case':index,'passed':row['passed'],'error':row.get('error')}),flush=True)
   part=next(p for p in parts if p['reference']=='R101');pending=await call('capture_plan_display_font',{'sessionId':sid,'partId':part['objectId'],'property':'Value','font':{'height':-19}});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_display_font',pk);await call('capture_apply_display_font',{**pk,'idempotencyKey':'pending'},'write_not_replayed');await call('capture_close',{'sessionId':sid});report['pendingCancel']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for index,row in enumerate(report['cases']):
    if not row['passed']:continue
    key={k:row['plan'][k] for k in ('planId','planDigest')};response=await fresh.call_tool('capture_apply_display_font',{**key,'idempotencyKey':f'font-{index}'});assert not response.is_error and not response.structured_content['data']['mutationReplayed'];response=await fresh.call_tool('capture_recover_display_font',key);assert not response.is_error
  report['freshNoReplay']=True;report['passed']=all(row['passed'] for row in report['cases'])
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'];dump()
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
