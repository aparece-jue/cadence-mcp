"""MCP update/delete on duplicate literal texts among32 mixed page graphics."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source);cases=[]
for mirror in (0,1):
 for rotation in range(4):cases.append({'operation':'update','textIndex':1,'change':{'text':f'修改文字 {rotation}/{mirror} [x]$;\n中文Ω','location':[400+rotation*20,500+mirror*40],'width':160,'height':35,'font':{'faceName':'Arial','height':-15,'weight':700,'underline':True},'rotation':rotation,'mirror':mirror}})
for index in (0,1,3):cases.append({'operation':'delete','textIndex':index})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','90'],env=env)
async def main():
 report={'passed':False,'cases':[],'checks':{},'sourceSha256':before,'oracleSha256':oracle}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   async def call(n,args):
    r=await c.call_tool(n,args);assert not r.is_error,(n,r.structured_content);return r.structured_content['data']
   report['tools']=len((await c.list_tools()).tools);assert report['tools']==200
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE');old=(await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':1000}))['items'];texts=[p for p in old if p['kind']=='text'];assert len(old)==32 and len(texts)==4 and len({p['localDescriptor'][1] for p in texts})==1
   for i,case in enumerate(cases):
    target=texts[case['textIndex']];args={'sessionId':sid,'graphicId':target['objectId'],'operation':case['operation'],**({'change':case['change']} if 'change' in case else {})};plan=await call('capture_plan_graphic_text_edit',args);keys={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_graphic_text_add',{**keys,'idempotencyKey':f'edit-{i}'})
    assert result['modeledGraphicsAndInstancesPreserved'];opened=await call('capture_open_edit_result',{**keys,'kind':'graphic_text'});pg=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE');rows=(await call('capture_query_page_vectors',{'sessionId':opened['sessionId'],'pageId':pg['objectId'],'limit':1000}))['items'];canonical=lambda p:{k:v for k,v in p.items() if k not in ('objectId','pageId','nativeId','nativeTypeCode','index')};expected=[canonical(p) for p in old];index=target['index']
    if case['operation']=='delete':
     del expected[index];assert result['graphicRemovalVerified'] and not result['pageAnchorVerified'];assert [canonical(p) for p in rows]==expected
    else:
     changed=case['change'];actual=rows[index];assert actual['kind']=='text' and actual['localDescriptor'][1]==changed['text'] and actual['pageControlPoints'][0]==changed['location'] and actual['rotationCode']==changed['rotation'] and actual['mirrorCode']==changed['mirror'];assert [canonical(p) for j,p in enumerate(rows) if j!=index]==[p for j,p in enumerate(expected) if j!=index];assert result['pageAnchorVerified'] and not result['graphicRemovalVerified']
    await call('capture_close',{'sessionId':opened['sessionId']});report['cases'].append({'case':case,'plan':plan,'result':result,'observedCount':len(rows)});print(json.dumps({'case':i,'operation':case['operation'],'passed':True}),flush=True)
   bads=[{'graphicId':old[0]['objectId'],'operation':'delete'},{'graphicId':'foreign/graphic-1','operation':'delete'},{'graphicId':texts[0]['objectId'],'operation':'update'},{'graphicId':texts[0]['objectId'],'operation':'delete','change':cases[0]['change']},{'graphicId':texts[0]['objectId'],'operation':'update','change':{**cases[0]['change'],'mirror':True}}]
   for bad in bads:assert (await c.call_tool('capture_plan_graphic_text_edit',{'sessionId':sid,**bad})).is_error
   pending=await call('capture_plan_graphic_text_edit',{'sessionId':sid,'graphicId':texts[0]['objectId'],'operation':'delete'});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_graphic_text_add',pk);assert (await c.call_tool('capture_apply_graphic_text_add',{**pk,'idempotencyKey':'cancelled-delete'})).is_error;await call('capture_close',{'sessionId':sid});assert (await c.call_tool('capture_plan_graphic_text_edit',{'sessionId':sid,'graphicId':texts[0]['objectId'],'operation':'delete'})).is_error;report['checks']['invalid_scope_type_update_delete_cancel_close']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for i in (0,8):
    plan=report['cases'][i]['plan'];keys={k:plan[k] for k in ('planId','planDigest')};same=await fresh.call_tool('capture_apply_graphic_text_add',{**keys,'idempotencyKey':f'edit-{i}'});assert not same.is_error and same.structured_content['data']['mutationReplayed'] is False;assert not (await fresh.call_tool('capture_recover_graphic_text_add',keys)).is_error
   report['checks']['fresh_update_delete_no_replay']=True
  report['passed']=True
 except BaseException as e:report['error']=str(e);report['traceback']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')},ensure_ascii=True),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
